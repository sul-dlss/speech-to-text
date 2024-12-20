resource "aws_placement_group" "placement" {
  name     = var.project_name
  strategy = "cluster"
}

resource "aws_batch_compute_environment" "compute_environment" {
  compute_environment_name_prefix = var.project_name

  compute_resources {
    instance_role = aws_iam_instance_profile.ecs_instance_role.arn
    #instance_role = "arn:aws:iam::482101366956:instance-profile/ecsInstanceRole"

    instance_type = [
      "m4.large",
    ]

    max_vcpus = 6 
    min_vcpus = 0

    placement_group = aws_placement_group.placement.name

    security_group_ids = [
      "sg-06d4cbb8f7150c41f"
    ]

    subnets = [
      "subnet-0cf5a854646151546"
    ]

    type = "EC2"
  }

  service_role = aws_iam_role.aws_batch_service_role.arn

  type         = "MANAGED"
  depends_on   = [
    aws_iam_role_policy_attachment.aws_batch_service_role
  ]

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_batch_job_definition" "job_definition" {
  name = var.project_name
  type = "container"

  container_properties = jsonencode({
    command = ["python3", "run.py"],
    image   = aws_ecr_repository.speech_to_text.repository_url

    logConfiguration = {
      logDriver = "awslogs"
    }

    resourceRequirements = [
      {
        type  = "VCPU"
        value = "1"
      },
      {
        type  = "MEMORY"
        value = "1024"
      }
    ]

    environment = [
      {
        name  = "VARNAME"
        value = "VARVAL"
      }
    ]

    command = [
      "--job",
      "Ref::job"
    ]
  })

  platform_capabilities = [
    "EC2"
  ]
}

resource "aws_batch_job_queue" "job_queue" {
  name     = var.project_name
  state    = "ENABLED"
  priority = 1

  compute_environment_order {
    order               = 1
    compute_environment = aws_batch_compute_environment.compute_environment.arn
  }
}
