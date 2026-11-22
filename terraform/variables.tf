variable "aiven_api_token" {
  description = "Token de API da Aiven. Passe via TF_VAR_aiven_api_token (nunca em arquivo versionado)."
  type        = string
  sensitive   = true
}

variable "aiven_project" {
  description = "Nome do projeto Aiven onde o serviço será criado."
  type        = string
}

variable "cloud_name" {
  description = "Região do serviço. Confirme no console/CLI quais regiões aceitam o plano gratuito."
  type        = string
  default     = "aws-us-east-1"
}

variable "pg_plan" {
  description = "Plano do PostgreSQL. Confira o nome do plano gratuito atual na documentação da Aiven."
  type        = string
  default     = "free-1-1gb"
}

variable "service_name" {
  description = "Nome do serviço PostgreSQL."
  type        = string
  default     = "pg-ods5-ods18-eleicoes"
}
