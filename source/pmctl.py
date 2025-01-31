import argparse
import base64
import os
import sys
import yaml
import time
import requests
from io import StringIO
from kubernetes import client, config
from kubernetes.client.rest import ApiException

class KubernetesPermissionManager:
    def __init__(self):
        # Load service account configuration from in-cluster config
        config.load_incluster_config()
        
        # Initialize Kubernetes API clients
        self.core_v1_api = client.CoreV1Api()
        self.rbac_v1_api = client.RbacAuthorizationV1Api()
        
        # Get the current namespace where the script is running
        with open('/var/run/secrets/kubernetes.io/serviceaccount/namespace', 'r') as f:
          self.manager_namespace = f.read().strip()
        
        # Environment variables for configuration
        self.control_plane_address = os.environ.get('CONTROL_PLANE_ADDRESS', 'https://kubernetes.default.svc')
        self.cluster_name = os.environ.get('CLUSTER_NAME', 'default-cluster')
        self.telegram_bot_api = os.environ.get('TELEGRAM_BOT_API')
        self.telegram_chat_id = os.environ.get('TELEGRAM_CHAT_ID')

    def send_file_to_telegram(self, file_content, filename):
        """
        Send a file to a Telegram chat using the Telegram Bot API.

        Args:
            file_content (str): The content of the file to send.
            filename (str): The name of the file.
        """
        if not self.telegram_bot_api or not self.telegram_chat_id:
            print("Error: Telegram Bot API token or chat ID not set.")
            return

        url = f"https://api.telegram.org/bot{self.telegram_bot_api}/sendDocument"
        files = {
            "document": (filename, StringIO(file_content), 'text/plain')
        }
        payload = {
            "chat_id": self.telegram_chat_id
        }

        try:
            response = requests.post(url, data=payload, files=files)
            response.raise_for_status()  # Raise an error for bad status codes
            print("File sent to Telegram successfully.")
        except requests.exceptions.RequestException as e:
            print(f"Error sending file to Telegram: {e}")

    def user_add(self, username):
        """
        Create a service account for the given username and ensure it has a token.
        
        Args:
            username (str): Name of the user/service account to create.
        """
        try:
            # Step 1: Create Service Account if it doesn't exist
            sa_manifest = client.V1ServiceAccount(
                metadata=client.V1ObjectMeta(name=username)
            )
            self.core_v1_api.create_namespaced_service_account(
                namespace=self.manager_namespace, 
                body=sa_manifest
            )
            print(f"Service Account '{username}' created successfully.")

        except ApiException as e:
            if e.status == 409:
                print(f"Service Account '{username}' already exists.")
            else:
                print(f"Unexpected error creating Service Account: {e}")
                sys.exit(1)
                
        time.sleep(1)
        # Step 2: Check if a Secret with a token exists for the ServiceAccount
        try:
            secrets = self.core_v1_api.list_namespaced_secret(self.manager_namespace)
            token_secret_name = None

            for secret in secrets.items:
                if secret.metadata.annotations and \
                   secret.metadata.annotations.get("kubernetes.io/service-account.name") == username:
                    token_secret_name = secret.metadata.name
                    break  # Stop if we find a matching token Secret
            
            # Step 3: If no token Secret is found, create one
            if not token_secret_name:
                token_secret_name = f"{username}-token"
                secret_manifest = client.V1Secret(
                    metadata=client.V1ObjectMeta(
                        name=token_secret_name,
                        annotations={"kubernetes.io/service-account.name": username}
                    ),
                    type="kubernetes.io/service-account-token"
                )
                self.core_v1_api.create_namespaced_secret(
                    namespace=self.manager_namespace, 
                    body=secret_manifest
                )
                print(f"Token Secret '{token_secret_name}' created for ServiceAccount '{username}'.")
            else:
                print(f"Token Secret '{token_secret_name}' already exists for ServiceAccount '{username}'.")

        except ApiException as e:
            print(f"Error while checking/creating token Secret: {e}")
            sys.exit(1)

    def user_remove(self, username):
        """
        Remove a service account and its associated token Secret for the given username.

        Args:
            username (str): Name of the user/service account to remove.
        """
        try:
            # Step 1: Find and Delete the Service Account Token Secret
            secrets = self.core_v1_api.list_namespaced_secret(self.manager_namespace)
            deleted_secret = None

            for secret in secrets.items:
                if secret.metadata.annotations and \
                secret.metadata.annotations.get("kubernetes.io/service-account.name") == username:
                    self.core_v1_api.delete_namespaced_secret(
                        name=secret.metadata.name,
                        namespace=self.manager_namespace
                    )
                    deleted_secret = secret.metadata.name
                    print(f"Deleted Token Secret '{deleted_secret}' for ServiceAccount '{username}'.")
                    break  # Stop after deleting the first matching token

            if not deleted_secret:
                print(f"No token Secret found for ServiceAccount '{username}', skipping Secret deletion.")

            # Step 2: Delete the Service Account
            self.core_v1_api.delete_namespaced_service_account(
                name=username,
                namespace=self.manager_namespace
            )
            print(f"Service Account '{username}' removed successfully.")

        except ApiException as e:
            if e.status == 404:
                print(f"Error: Service Account '{username}' does not exist.")
                sys.exit(1)
            else:
                print(f"Unexpected error removing Service Account: {e}")
                sys.exit(1)


    def user_list(self):
        """
        List all service accounts in the manager's namespace
        """
        sa_list = self.core_v1_api.list_namespaced_service_account(namespace=self.manager_namespace)
        if not sa_list.items:
            print("No service accounts found.")
        else:
            print("Service Accounts:")
            for sa in sa_list.items:
                print(f"- {sa.metadata.name}")

    def user_describe(self, username):
        """
        Describe permissions for a specific user/service account
        
        Args:
            username (str): Name of the user/service account to describe
        """
        # Collect Namespace Role Bindings
        ns_permissions = {}
        rb_list = []
        continue_token = None  # Used for pagination
        while True:
            role_binding_list = self.rbac_v1_api.list_role_binding_for_all_namespaces(limit=100, _continue=continue_token)
            for rb in role_binding_list.items:
                if rb.subjects:
                    for sub in rb.subjects:
                        if sub.name == username:
                            rb_list.append(rb)
                            break
            continue_token = role_binding_list.metadata._continue
            if not continue_token:
                break

        for rb in rb_list:
            namespace = rb.metadata.namespace
            role_ref = rb.role_ref.name
            
            ns_permissions.setdefault(namespace, {})
            ns_permissions[namespace][role_ref.split('___')[1]] = True

        cluster_permissions = {}

        # Fetch all ClusterRoleBindings
        crb_list = self.rbac_v1_api.list_cluster_role_binding()

        # Filter for the user's ClusterRoleBindings
        for crb in crb_list.items:
            if crb.subjects:
                for sub in crb.subjects:
                    if sub.name == username:
                        role_ref = crb.role_ref.name
                        if "___" in role_ref:
                            cluster_permissions[role_ref.split('___')[1]] = True
                        else:
                            cluster_permissions[role_ref] = True  # Fallback if no "___" delimiter
                        break  # Stop checking other subjects in this CRB once found


        # Print Namespace Permissions
        if ns_permissions:
            print("Namespace:")
            for ns, perms in ns_permissions.items():
                print(f"  - {ns}:")
                for perm, _ in perms.items():
                    print(f"      - {perm}")

        # Print Cluster Permissions
        if cluster_permissions:
            print("Cluster:")
            for perm, _ in cluster_permissions.items():
                print(f"  - {perm}")

    def ns_grant(self, username, namespace, permission):
        """
        Grant namespace-level permissions to a user
        
        Args:
            username (str): Name of the user/service account
            namespace (str): Target namespace
            permission (str): Permission level (developer, operation, monitoring)
        """
        role_binding_name = f"{username}___template-namespaced-resources___{permission}___{namespace}"
        role_name = f"template-namespaced-resources___{permission}"

        try:
            # Create Role Binding
            rb_manifest = client.V1RoleBinding(
                metadata=client.V1ObjectMeta(
                    name=role_binding_name,
                    namespace=namespace
                ),
                role_ref=client.V1RoleRef(
                    api_group='rbac.authorization.k8s.io',
                    kind='ClusterRole',
                    name=role_name
                ),
                subjects=[
                    client.RbacV1Subject(
                        kind='ServiceAccount',
                        name=username,
                        namespace=self.manager_namespace
                    )
                ]
            )
            
            self.rbac_v1_api.create_namespaced_role_binding(
                namespace=namespace, 
                body=rb_manifest
            )
            print(f"Granted {permission} permissions to {username} in namespace {namespace}")
        
        except ApiException as e:
            if e.status == 409:
                print(f"Warning: Role binding {role_binding_name} already exists.")
            else:
                print(f"Unexpected error granting permissions: {e}")
                sys.exit(1)

    def ns_revoke(self, username, namespace, permission):
        """
        Revoke namespace-level permissions from a user
        
        Args:
            username (str): Name of the user/service account
            namespace (str): Target namespace
            permission (str): Permission level to revoke
        """
        role_binding_name = f"{username}___template-namespaced-resources___{permission}___{namespace}"
        
        # Confirm revocation
        confirm = input(f"Are you sure you want to revoke {permission} permissions for {username} in {namespace}? (y/N): ")
        if confirm.lower() not in ['y', '']:
            print("Operation cancelled.")
            return

        try:
            self.rbac_v1_api.delete_namespaced_role_binding(
                name=role_binding_name, 
                namespace=namespace
            )
            print(f"Revoked {permission} permissions from {username} in namespace {namespace}")
        
        except ApiException as e:
            if e.status == 404:
                print(f"Error: Role binding {role_binding_name} does not exist.")
                sys.exit(1)
            else:
                print(f"Unexpected error revoking permissions: {e}")
                sys.exit(1)

    def ns_print(self, username, namespace, output_type='std'):
        """
        Print kubeconfig for a specific user and namespace
        
        Args:
            username (str): Name of the user/service account
            namespace (str): Target namespace
            output_type (str): Output method (std or telegram)
        """
        try:
            secrets = self.core_v1_api.list_namespaced_secret(self.manager_namespace)
            sa_secrets = None

            for secret in secrets.items:
                if secret.metadata.annotations and \
                secret.metadata.annotations.get("kubernetes.io/service-account.name") == username:
                    sa_secrets = secret
                    break  # Stop after deleting the first matching token
        
            if not sa_secrets:
                print(f"Error: No token secret found for {username}")
                sys.exit(1)
            
            # Decode token and CA certificate
            token = base64.b64decode(sa_secrets.data['token']).decode('utf-8')
            ca_cert = sa_secrets.data['ca.crt']

            # Generate kubeconfig
            kubeconfig = {
                'apiVersion': 'v1',
                'kind': 'Config',
                'current-context': f"{username}-{namespace}",
                'clusters': [{
                    'cluster': {
                        'certificate-authority-data': ca_cert,
                        'server': self.control_plane_address
                    },
                    'name': self.cluster_name
                }],
                'contexts': [{
                    'context': {
                        'cluster': self.cluster_name,
                        'user': username,
                        'namespace': namespace
                    },
                    'name': f"{username}-{namespace}"
                }],
                'users': [{
                    'name': username,
                    'user': {
                        'token': token
                    }
                }]
            }

            kubeconfig_yaml = yaml.safe_dump(kubeconfig, default_flow_style=False)
            
            # Output handling
            if output_type == 'std':
                yaml.safe_dump(kubeconfig, sys.stdout, default_flow_style=False)
            elif output_type == 'telegram':
                # Send as a .txt file
                filename = f"kubeconfig_{username}_{namespace}.txt"
                self.send_file_to_telegram(kubeconfig_yaml, filename)
            else:
                print(f"Error: Invalid output type '{output_type}'.")
                sys.exit(1)
        
        except Exception as e:
            print(f"Error generating kubeconfig: {e}")
            sys.exit(1)

    def cluster_grant(self, username, permission):
        """
        Grant cluster-level permissions to a user
        
        Args:
            username (str): Name of the user/service account
            permission (str): Cluster permission level (read-only, admin)
        """
        cluster_role_binding_name = f"{username}___template-cluster-resources___{permission}"
        cluster_role_name = f"template-cluster-resources___{permission}"

        try:
            # Create Cluster Role Binding
            crb_manifest = client.V1ClusterRoleBinding(
                metadata=client.V1ObjectMeta(name=cluster_role_binding_name),
                role_ref=client.V1RoleRef(
                    api_group='rbac.authorization.k8s.io',
                    kind='ClusterRole',
                    name=cluster_role_name
                ),
                subjects=[
                    client.RbacV1Subject(
                        kind='ServiceAccount',
                        name=username,
                        namespace=self.manager_namespace
                    )
                ]
            )
            
            self.rbac_v1_api.create_cluster_role_binding(body=crb_manifest)
            print(f"Granted {permission} cluster permissions to {username}")
        
        except ApiException as e:
            if e.status == 409:
                print(f"Warning: Cluster role binding {cluster_role_binding_name} already exists.")
            else:
                print(f"Unexpected error granting cluster permissions: {e}")
                sys.exit(1)

    def cluster_revoke(self, username, permission):
        """
        Revoke cluster-level permissions from a user
        
        Args:
            username (str): Name of the user/service account
            permission (str): Cluster permission level to revoke
        """
        cluster_role_binding_name = f"{username}___template-cluster-resources___{permission}"
        
        # Confirm revocation
        confirm = input(f"Are you sure you want to revoke {permission} cluster permissions for {username}? (y/N): ")
        if confirm.lower() not in ['y', '']:
            print("Operation cancelled.")
            return

        try:
            self.rbac_v1_api.delete_cluster_role_binding(
                name=cluster_role_binding_name
            )
            print(f"Revoked {permission} cluster permissions from {username}")
        
        except ApiException as e:
            if e.status == 404:
                print(f"Error: Cluster role binding {cluster_role_binding_name} does not exist.")
                sys.exit(1)
            else:
                print(f"Unexpected error revoking cluster permissions: {e}")
                sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description='Kubernetes Permission Management CLI')
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # User management commands
    user_add_parser = subparsers.add_parser('user', help='User management')
    user_add_subparsers = user_add_parser.add_subparsers(dest='user_command')

    add_parser = user_add_subparsers.add_parser('add', help='Add a new user')
    add_parser.add_argument('username', help='Username to add')

    remove_parser = user_add_subparsers.add_parser('remove', help='Remove a user')
    remove_parser.add_argument('username', help='Username to remove')

    list_parser = user_add_subparsers.add_parser('list', help='List users')
    
    describe_parser = user_add_subparsers.add_parser('describe', help='Describe user permissions')
    describe_parser.add_argument('username', help='Username to describe')

    # Namespace permission commands
    ns_parser = subparsers.add_parser('ns', help='Namespace permission management')
    ns_subparsers = ns_parser.add_subparsers(dest='ns_command')

    grant_parser = ns_subparsers.add_parser('grant', help='Grant namespace permissions')
    grant_parser.add_argument('username', help='Username')
    grant_parser.add_argument('namespace', help='Target namespace')
    grant_parser.add_argument('permission', choices=['developer', 'operation', 'monitoring'], help='Permission level')

    revoke_parser = ns_subparsers.add_parser('revoke', help='Revoke namespace permissions')
    revoke_parser.add_argument('username', help='Username')
    revoke_parser.add_argument('namespace', help='Target namespace')
    revoke_parser.add_argument('permission', choices=['developer', 'operation', 'monitoring'], help='Permission level')

    print_parser = ns_subparsers.add_parser('print', help='Print kubeconfig')
    print_parser.add_argument('username', help='Username')
    print_parser.add_argument('namespace', help='Target namespace')
    print_parser.add_argument('--output', choices=['std', 'telegram'], default='std', help='Output method (default: std)')

    # Cluster permission commands
    cluster_parser = subparsers.add_parser('cluster', help='Cluster permission management')
    cluster_subparsers = cluster_parser.add_subparsers(dest='cluster_command')

    cluster_grant_parser = cluster_subparsers.add_parser('grant', help='Grant cluster permissions')
    cluster_grant_parser.add_argument('username', help='Username')
    cluster_grant_parser.add_argument('permission', choices=['read-only', 'admin'], help='Permission level')

    cluster_revoke_parser = cluster_subparsers.add_parser('revoke', help='Revoke cluster permissions')
    cluster_revoke_parser.add_argument('username', help='Username')
    cluster_revoke_parser.add_argument('permission', choices=['read-only', 'admin'], help='Permission level')

    # Parse arguments
    args = parser.parse_args()

    # Initialize the permission manager
    manager = KubernetesPermissionManager()

    # Execute the appropriate command
    if args.command == 'user':
        if args.user_command == 'add':
            manager.user_add(args.username)
        elif args.user_command == 'remove':
            manager.user_remove(args.username)
        elif args.user_command in ['list', 'ls']:
            manager.user_list()
        elif args.user_command == 'describe':
            manager.user_describe(args.username)

    elif args.command == 'ns':
        if args.ns_command == 'grant':
            manager.ns_grant(args.username, args.namespace, args.permission)
        elif args.ns_command == 'revoke':
            manager.ns_revoke(args.username, args.namespace, args.permission)
        elif args.ns_command == 'print':
            manager.ns_print(args.username, args.namespace, args.output)

    elif args.command == 'cluster':
        if args.cluster_command == 'grant':
            manager.cluster_grant(args.username, args.permission)
        elif args.cluster_command == 'revoke':
            manager.cluster_revoke(args.username, args.permission)

    else:
        parser.print_help()
        sys.exit(1)

if __name__ == '__main__':
    main()
