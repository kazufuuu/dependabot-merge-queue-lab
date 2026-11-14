variable "environment" {
  type = string
}

resource "random_pet" "bucket_suffix" {
  length    = 2
  separator = "-"
  keepers = {
    environment = var.environment
  }
}

resource "null_resource" "marker" {
  triggers = {
    bucket = local.bucket_name
  }
}

locals {
  bucket_name = "contacts-${var.environment}-${random_pet.bucket_suffix.id}"
}

output "bucket_name" {
  value = local.bucket_name
}
