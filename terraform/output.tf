output "s3_bucket" {
  value = aws_s3_bucket.speech_to_text_bucket.arn
}

output "done_queue" {
  value = aws_sqs_queue.done_queue.arn
}

output "docker_repository" {
  value = aws_ecr_repository.speech_to_text.repository_url
}

output "compute_environment" {
  value = aws_batch_compute_environment.compute_environment.arn
}

output "job_definition" {
  value = aws_batch_job_definition.job_definition.arn
}

output "job_queue" {
  value = aws_batch_job_queue.job_queue.arn
}
