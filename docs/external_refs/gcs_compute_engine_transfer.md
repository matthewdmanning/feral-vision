# Cloud Storage transfer to an internal-only Compute Engine VM

## Finding

A training VM should stage a Dataset from Cloud Storage with its attached
service account and the Cloud Storage API; it does not need public-internet
egress merely to download `gs://` objects. For a VM without an external IP,
the VM's subnet must enable Private Google Access. The VPC must also retain an
appropriate route to the default internet gateway and allow the required
Google API egress; traffic to Google APIs stays within Google's network even
though that route is named the default internet gateway.

Use `gcloud storage cp --recursive gs://<bucket>/<dataset-prefix>/payload/
<mounted-ssd>/` (or a Cloud Storage client library) to stage the explicit
dataset prefix. This is a Google-supported recursive-download mechanism; do
not enumerate image paths across bucket prefixes.

The VM's attached user-managed service account needs least-privilege Cloud
Storage IAM on the selected bucket/prefix. `roles/storage.objectViewer` is
sufficient for object reads; the recommended VM OAuth scope is
`https://www.googleapis.com/auth/cloud-platform`, with IAM roles restricting
what the application can do.

## What Private Google Access does not provide

Private Google Access reaches Google APIs such as Cloud Storage. It does not
provide general public-internet access. Public Cloud NAT (or an external IP)
is only needed when the VM must reach non-Google endpoints, for example Debian
or PyPI package repositories. Therefore, a production training image should
already contain `gcloud`/the relevant client library and DVC dependencies when
the Cloud Job is intentionally internal-only; its Dataset staging then needs
Private Google Access and service-account IAM, not Cloud NAT.

## Official sources

- [Configure Private Google Access](https://cloud.google.com/vpc/docs/configure-private-google-access): Internal-only VMs can access Google APIs when Private Google Access is enabled on their subnet; the page also specifies route and firewall requirements and states that Google API traffic remains within Google's network.
- [Private Google Access overview](https://cloud.google.com/vpc/docs/private-google-access): Confirms that internal-only VMs can reach Cloud Storage with Private Google Access, while VMs with an external IP do not need it.
- [Cloud Storage: Download objects](https://cloud.google.com/storage/docs/downloading-objects): Recommends `gcloud storage cp` or a client library for recursive object downloads and identifies `roles/storage.objectViewer` as the normal download role.
- [Compute Engine service accounts](https://cloud.google.com/compute/docs/access/service-accounts): Recommends a user-managed service account, the `cloud-platform` access scope, and IAM roles for least-privilege API access.
- [Cloud NAT overview](https://cloud.google.com/nat/docs/overview): Defines Public NAT as outbound connectivity for resources without external IPv4 addresses that need to reach IPv4 destinations on the internet.
