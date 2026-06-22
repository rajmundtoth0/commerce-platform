# Scaleway staging infrastructure for commerce-platform.
# Creates: Kapsule cluster + node pool, Managed PostgreSQL (+3 databases),
# Managed Redis, and a Container Registry namespace.

# --- Kubernetes (Kapsule) -------------------------------------------------
resource "scaleway_k8s_cluster" "stg" {
  name                        = var.cluster_name
  version                     = var.k8s_version
  cni                         = "cilium"
  type                        = "kapsule"
  delete_additional_resources = true
  tags                        = ["commerce-platform", "stg"]
}

resource "scaleway_k8s_pool" "stg" {
  cluster_id  = scaleway_k8s_cluster.stg.id
  name        = "default"
  node_type   = var.node_type
  size        = var.node_pool_min
  min_size    = var.node_pool_min
  max_size    = var.node_pool_max
  autoscaling = true
  autohealing = true
  zone        = var.zone
}

# --- Managed PostgreSQL (source of truth per service) ---------------------
resource "scaleway_rdb_instance" "pg" {
  name              = "commerce-stg-pg"
  node_type         = var.pg_node_type
  engine            = var.pg_engine
  is_ha_cluster     = false
  disable_backup    = false
  user_name         = var.pg_user
  password          = var.pg_password
  volume_type       = "bssd"
  volume_size_in_gb = var.pg_volume_size_gb
  tags              = ["commerce-platform", "stg"]
}

# One database per owning service (matches the per-service ownership model).
resource "scaleway_rdb_database" "dbs" {
  for_each    = toset(["auth", "orders", "backoffice"])
  instance_id = scaleway_rdb_instance.pg.id
  name        = each.key
}

# --- Managed Redis (Valkey-compatible; TLS) -------------------------------
resource "scaleway_redis_cluster" "valkey" {
  name         = "commerce-stg-redis"
  version      = var.redis_version
  node_type    = var.redis_node_type
  user_name    = "commerce"
  password     = var.redis_password
  cluster_size = 1
  tls_enabled  = true
  tags         = ["commerce-platform", "stg"]
}

# --- Container Registry ---------------------------------------------------
resource "scaleway_registry_namespace" "reg" {
  name      = var.registry_namespace
  region    = var.region
  is_public = false
}
