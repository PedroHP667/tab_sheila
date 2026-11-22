output "postgres_uri" {
  description = "URI de conexão (contém senha). Use: terraform output -raw postgres_uri"
  value       = aiven_pg.eleicoes.service_uri
  sensitive   = true
}

output "postgres_host" {
  value = aiven_pg.eleicoes.service_host
}

output "postgres_port" {
  value = aiven_pg.eleicoes.service_port
}
