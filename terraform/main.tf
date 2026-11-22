terraform {
  required_version = ">= 1.5"

  required_providers {
    aiven = {
      source  = "aiven/aiven"
      version = "~> 4.0"
    }
  }
}

provider "aiven" {
  api_token = var.aiven_api_token
}

# Banco principal (Aiven for PostgreSQL - plano gratuito)
resource "aiven_pg" "eleicoes" {
  project                = var.aiven_project
  cloud_name             = var.cloud_name
  plan                   = var.pg_plan
  service_name           = var.service_name
  termination_protection = false

  pg_user_config {
    pg_version = "16"
  }
}
