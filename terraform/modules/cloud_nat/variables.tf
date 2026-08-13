variable "router_name" {
  description = "Cloud Router name."
  type        = string
  nullable    = false
}

variable "nat_name" {
  description = "Cloud NAT name."
  type        = string
  nullable    = false
}

variable "network" {
  description = "VPC network self-link for the Cloud Router."
  type        = string
  nullable    = false
}

variable "region" {
  description = "Region containing the Cloud Router and NAT."
  type        = string
  nullable    = false
}

variable "subnetwork" {
  description = "Subnetwork self-link served by Cloud NAT."
  type        = string
  nullable    = false
}

variable "nat_ip_allocate_option" {
  description = "Cloud NAT external IP allocation mode."
  type        = string
  default     = "AUTO_ONLY"
  nullable    = false
}

variable "source_subnetwork_ip_ranges_to_nat" {
  description = "Cloud NAT source subnetwork range mode."
  type        = string
  default     = "LIST_OF_SUBNETWORKS"
  nullable    = false
}

variable "source_ip_ranges_to_nat" {
  description = "Source IP ranges from the selected subnetwork served by Cloud NAT."
  type        = list(string)
  default     = ["ALL_IP_RANGES"]
  nullable    = false
}
