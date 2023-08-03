#!/bin/bash

usage_comment="Usage: $0 <step path>";

# TODO: support a "singularity" or "docker" input arg
# TODO: support user-provided input files
# e.g. docker cp some-directory/* $image_id:/app/ 

if [[ -z "$1" ]]; then
    echo $usage_comment
    echo "Please provide the step-specific directory."
    exit 1
fi

dir=$(realpath "$1");
step=$(basename $dir);

# TODO: implement versioning
mkdir $dir/results

echo "" &&
echo "Loading image" &&
docker load -i $dir/step.tar &&
image_id=$(docker images --filter=reference=$step --format "{{.ID}}")
echo "" &&
echo "Running the step" &&
docker run --rm -v $dir:/app $image_id 2>&1 | tee $dir/results/$step.o &&
# TODO: mount the results folder and move it in the container itself
mv census_2030_with_piks_sample.parquet $dir/results &&
echo "" &&
echo "Removing image" &&
docker rmi $image_id &&
echo "" &&
echo "*** finished ***" &&
echo ""