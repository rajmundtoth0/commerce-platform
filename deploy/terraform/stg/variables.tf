variable "project_id" {
  type        = string
  description = "Scaleway project ID."
}

variable "region" {
  type    = string
  default = "fr-par"
}

variable "zone" {
  type    = string
  default = "fr-par-1"
}

variable "cluster_name" {
  type    = string
  default = "commerce-stg"
}

variable "k8s_version" {
  type    = string
  default = "1.31"
}

# Node types: check availability with `scw k8s node-type list`.
variable "node_type" {
  type    = string
  default = "PLAY2-NANO"
}

variable "node_pool_min" {
  type    = number
  default = 2
}

variable "node_pool_max" {
  type    = number
  default = 4
}

# --- Managed PostgreSQL ---------------------------------------------------
variable "pg_node_type" {
  type    = string
  default = "DB-DEV-S"
}

variable "pg_engine" {
  type    = string
  default = "PostgreSQL-15"
}

variable "pg_user" {
  type    = string
  default = "commerce"
}

variable "pg_password" {
  type        = string
  sensitive   = true
  description = "Password for the managed Postgres user (also put it in the k8s Secret commerce-postgres)."
}

variable "pg_volume_size_gb" {
  type    = number
  default = 10
}

# --- Managed Redis (Valkey-compatible) ------------------------------------
variable "redis_node_type" {
  type    = string
  default = "RED1-MICRO"
}

variable "redis_version" {
  type    = string
  default = "7.0.5"
}

variable "redis_password" {
  type      = string
  sensitive = true
}

variable "registry_namespace" {
  type    = string
  default = "commerce-stg"
}
