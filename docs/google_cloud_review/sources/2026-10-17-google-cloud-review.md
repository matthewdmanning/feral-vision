# Google Cloud review: container startup sources

Verified against first-party documentation on 2026-10-17. These are platform
facts and design implications, not proof of any deployed resource.

## Docker process and restart behavior

- `no` is the default restart policy. `on-failure[:max-retries]` retries nonzero
  exits but does not restart a container when the daemon restarts. `always`
  restarts stopped containers, including after successful completion.
  [Docker restart policies](https://docs.docker.com/engine/containers/start-containers-automatically/#use-a-restart-policy)
- Docker documents a successful-start monitoring threshold of ten seconds.
  An attached foreground CLI exits when the container stops even if the restart
  policy subsequently restarts it. Docker warns against combining restart
  policies with host process managers.
  [Docker policy details](https://docs.docker.com/engine/containers/start-containers-automatically/#restart-policy-details)
- **Design inference:** completed batch training must not use `always` as an
  automatic retry mechanism. Choose one retry owner; preserve exit evidence and
  require explicit recovery after failure rather than silently retraining.
- Exec-form `ENTRYPOINT` receives appended runtime arguments. Shell-form
  entrypoints introduce a shell that does not forward signals to the executable.
  A wrapper can replace itself with `exec` so the final process receives signals;
  wrappers retaining postprocessing responsibilities must forward signals and wait.
  [Docker ENTRYPOINT](https://docs.docker.com/reference/dockerfile/#entrypoint)
- **Design inference:** staging can precede `exec` into training. If output upload
  must run after training, retain a deliberate supervisor with signal forwarding
  and the original training exit status; merely adding an EXIT trap to a wrapper
  that then executes `exec` does not provide that postprocessing.

## Compute Engine startup behavior

- Linux startup scripts run as root when the VM boots and require available
  networking. The guest environment must be installed and running; public
  Compute Engine images include it, custom images require explicit verification.
  Metadata can contain a script or a Cloud Storage script URL. If both are used,
  inline scripts precede URL scripts on subsequent boots.
  [Linux startup scripts](https://docs.cloud.google.com/compute/docs/instances/startup-scripts/linux)
- Scripts can also be rerun manually. Their output is available through the
  startup-script systemd journal and serial port 1.
  [Rerun and inspect scripts](https://docs.cloud.google.com/compute/docs/instances/startup-scripts/linux#rerunning_a_linux_startup_script)
- **Design inference:** boot is a repeatable trigger, not a one-time transaction.
  Serialize invocations, check retained container/job identity and terminal state,
  and do not create a second training process merely because startup runs again.
  VM creation success alone does not demonstrate successful staging or training.

## Load-bearing checks suggested by these facts

- Execute startup twice and concurrently against a controlled Docker boundary:
  assert only one training execution and preserved successful terminal state.
- Interrupt the actual entrypoint and verify signal delivery, bounded shutdown,
  output publication policy, and a failure status that reaches the operator.
- Simulate missing input and failed staging: assert training never starts and
  the failure identifies the missing object rather than claiming completion.

No cloud resources, credentials, production containers, or GPU behavior were
inspected by this research task; those require separate SDK/CLI verification.
