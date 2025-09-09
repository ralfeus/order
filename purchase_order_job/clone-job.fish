#!/usr/bin/env fish

function clone_aws_batch_job
    if test (count $argv) -ne 1
        echo "Usage: clone_aws_batch_job <original-job-id>"
        return 1
    end

    set original_job_id $argv[1]

    # Describe the original job and capture output
    set job_desc (aws batch describe-jobs --jobs $original_job_id)

    if test -z "$job_desc"
        echo "Failed to get job description for job ID $original_job_id"
        return 1
    end

    # Extract jobDefinition, jobQueue, containerOverrides, parameters, original jobName
    set job_definition (echo $job_desc | jq -r '.jobs[0].jobDefinition')
    set job_queue (echo $job_desc | jq -r '.jobs[0].jobQueue')
    set original_job_name test-po-us
    set parameters (echo $job_desc | jq -c '.jobs[0].parameters')

    set env_vars (echo $job_desc | jq -c '.jobs[0].container.environment')
    set container_overrides (echo "{\"environment\": $env_vars}")

    # New job name based on original plus timestamp
    set timestamp (date '+%Y%m%d%H%M%S')
    set new_job_name "$original_job_name-$timestamp"

    # Prepare container overrides argument
    set container_overrides_arg
    if test "$container_overrides" != "null"
        set container_overrides_arg "--container-overrides" "$container_overrides"
    end

    # Prepare parameters argument
    set parameters_arg
    if test "$parameters" != "null"
        set parameters_arg "--parameters" "$parameters"
    end

    # Submit the cloned job
    echo "Submitting cloned job with name: $new_job_name"
    aws batch submit-job \
        --job-name $new_job_name \
        --job-queue $job_queue \
        --job-definition $job_definition \
        $container_overrides_arg \
        $parameters_arg
end

# Run the function with the passed argument
clone_aws_batch_job $argv[1]
