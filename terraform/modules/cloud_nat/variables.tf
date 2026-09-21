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

variable "nat_ip_allocate_option" {
  description = "Cloud NAT external IP allocation mode."
  type        = string
  default     = "AUTO_ONLY"
  nullable    = false
}
