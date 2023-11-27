# Stage 1: Start with the miniconda3 base image
FROM continuumio/miniconda3 as conda-base

# Setup I/O directories and copy the environment and Python script
RUN mkdir -p /input_data
RUN mkdir -p /results
VOLUME /results
VOLUME /input_data
COPY person_linkage_case_study_sample_data_spark_local.py person_linkage_case_study_spark_local_lock_no_jupyter.txt ./

# Create a new conda environment
SHELL ["/bin/bash", "--login", "-c"]
RUN conda init bash \
    && . ~/.bashrc \
    && conda create -n person_linkage_case_study_spark_local --file=person_linkage_case_study_spark_local_lock_no_jupyter.txt

# Stage 2: Start with the Apache Spark base image
FROM apache/spark as spark-base

COPY --from=conda-base /opt/conda /opt/conda
COPY --from=conda-base person_linkage_case_study_sample_data_spark_local.py ./

# Set PATH for conda environment and conda itself
ENV PATH=/opt/conda/envs/person_linkage_case_study_spark_local/bin:/opt/conda/condabin:${PATH}

# Run your script with Spark on startup
CMD ["/bin/bash", "-c", "conda run -n person_linkage_case_study_spark_local python /opt/spark/work-dir/person_linkage_case_study_sample_data_spark_local.py \
     && mv census_2030_with_piks_sample.parquet /results/"]
