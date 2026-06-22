output "kubeconfig" {
  description = "Write to a file and `export KUBECONFIG=...` (or use `scw k8s kubeconfig install`)."
  value       = scaleway_k8s_cluster.stg.kubeconfig[0].config_file
  sensitive   = true
}

output "cluster_id" {
  value = scaleway_k8s_cluster.stg.id
}

output "registry_endpoint" {
  description = "Set as global.image.pyRepository/uiRepository prefix in values-stg.yaml."
  value       = scaleway_registry_namespace.reg.endpoint
}

output "postgres_host" {
  description = "global.postgres.host in values-stg.yaml."
  value       = try(scaleway_rdb_instance.pg.load_balancer[0].hostname, scaleway_rdb_instance.pg.load_balancer[0].ip)
}

output "postgres_port" {
  value = try(scaleway_rdb_instance.pg.load_balancer[0].port, 5432)
}

output "redis_id" {
  description = "Fetch the endpoint with: scw redis cluster get <id> (host:port -> global.valkey.* as rediss://)."
  value       = scaleway_redis_cluster.valkey.id
}
