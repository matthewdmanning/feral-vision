variable "name" {
  description = "Existing subnetwork name."
  type        = string
  nullable    = false
}

variable "network" {
  description = "Existing VPC network self-link."
  type        = string
  nullable    = false
}

variable "region" {
  description = "Region containing the existing subnetwork."
  type        = string
  nullable    = false
}

variable "ip_cidr_range" {
  description = "Existing subnetwork IPv4 CIDR range."
  type        = string
  nullable    = false
}

variable "private_ip_google_access" {
  description = "Whether the subnetwork enables Private Google Access."
  type        = bool
  default     = true
  nullable    = false
}
