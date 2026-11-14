variables {
  environment = "test"
}

run "bucket_name_has_environment_and_suffix" {
  command = apply

  assert {
    condition     = can(regex("^contacts-test-[a-z]+-[a-z]+$", output.bucket_name))
    error_message = "bucket 名は contacts-<環境>-<2 語> の形にする"
  }

  assert {
    condition     = null_resource.marker.triggers.bucket == output.bucket_name
    error_message = "marker は bucket 名を持つ"
  }
}
