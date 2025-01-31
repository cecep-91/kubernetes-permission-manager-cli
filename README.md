# Kubernetes Permission Manager CLI

The **Kubernetes Permission Manager CLI** is a command-line tool designed to simplify user and permission management in Kubernetes clusters. Inspired by [SIGHUP's Permission Manager](https://github.com/sighupio/permission-manager), this CLI provides an intuitive interface for managing users, granting and revoking namespace and cluster-level permissions, and generating kubeconfig files. This project support latest kubernetes version.

---

## Features

- **User Management**: Add, remove, list, and describe users.
- **Namespace Permissions**: Grant or revoke permissions (`developer`, `operation`, `monitoring`) for specific namespaces.
- **Cluster Permissions**: Grant or revoke cluster-wide permissions (`read-only`, `admin`).
- **Kubeconfig Generation**: Print kubeconfig files for users in a specific namespace, with support for multiple output methods.

---

## Installation

The Kubernetes Permission Manager CLI can be installed using Helm. Follow the steps below to deploy the application to your Kubernetes cluster.

### Prerequisites

1. A running Kubernetes cluster.
2. Helm installed on your local machine. If you don't have Helm installed, follow the [official Helm installation guide](https://helm.sh/docs/intro/install/).

### Steps to Install

1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/permission-manager-cli.git
   cd permission-manager-cli
   ```

2. Edit `values.yaml` based on your needs.

3. Install the Helm chart:
   ```bash
   helm install permission-manager ./charts
   ```

   This will deploy the Permission Manager CLI to your Kubernetes cluster.

4. Verify the installation:
   ```bash
   kubectl get pods -l app=permission-manager
   ```

   Ensure the pod is running before proceeding.

---

## Usage

Once the Permission Manager CLI is deployed, you can interact with it by executing commands inside the running pod.

### Exec into the Pod

1. Get the name of the running pod:
   ```bash
   kubectl get pods -l app=permission-manager
   ```

   Example output:
   ```
   NAME                                  READY   STATUS    RESTARTS   AGE
   permission-manager-cli-5f7c8d6c4b-abcde   1/1     Running   0          2m
   ```

2. Exec into the pod:
   ```bash
   kubectl exec -it permission-manager-5f7c8d6c4b-abcde -- /bin/fish
   ```

3. Run the CLI commands from within the pod. For example:
   ```bash
   pmctl user add cecep
   ```

---

### User Management

#### Add a User
Add a new user to the system.
```bash
pmctl user add <username>
```

#### Remove a User
Remove an existing user from the system.
```bash
pmctl user remove <username>
```

#### List Users
List all users in the system.
```bash
pmctl user list
```

#### Describe User Permissions
Describe the permissions of a specific user.
```bash
pmctl user describe <username>
```

---

### Namespace Permissions

#### Grant Permissions
Grant a user specific permissions (`developer`, `operation`, `monitoring`) in a namespace.
```bash
pmctl ns grant <username> <namespace> <permission>
```

#### Revoke Permissions
Revoke a user's permissions in a namespace.
```bash
pmctl ns revoke <username> <namespace> <permission>
```

#### Print Kubeconfig
Generate and print a kubeconfig file for a user in a specific namespace. Supports `std` (standard output) and `telegram` output methods.
```bash
pmctl ns print <username> <namespace> [--output <std|telegram>]
```

---

### Cluster Permissions

#### Grant Cluster Permissions
Grant a user cluster-wide permissions (`read-only`, `admin`).
```bash
pmctl cluster grant <username> <permission>
```

#### Revoke Cluster Permissions
Revoke a user's cluster-wide permissions.
```bash
pmctl cluster revoke <username> <permission>
```

---

## Examples

1. Add a new user:
   ```bash
   pmctl user add cecep
   ```

2. Grant `developer` permissions to a user in the `staging` namespace:
   ```bash
   pmctl ns grant cecep staging developer
   ```

3. Print a kubeconfig file for a user in the `staging` namespace:
   ```bash
   pmctl ns print cecep staging --output std
   ```

4. Grant `admin` permissions to a user at the cluster level:
   ```bash
   pmctl cluster grant cecep admin
   ```

---

## Contributing

Contributions are welcome! If you'd like to contribute, please follow these steps:

1. Fork the repository.
2. Create a new branch for your feature or bugfix.
3. Commit your changes and push to your fork.
4. Submit a pull request with a detailed description of your changes.

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

## Acknowledgments

- Inspired by [SIGHUP's Permission Manager](https://github.com/sighupio/permission-manager).
- Built with ❤️ for Kubernetes enthusiasts.

---

For any questions or issues, please open an issue on the [GitHub repository](https://github.com/cecep-91/kubernetes-permission-manager-cli).