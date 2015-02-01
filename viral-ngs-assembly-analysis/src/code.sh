#!/bin/bash

main() {
    set -e -x -o pipefail

    if [ -z "$name" ]; then
        name="${assembly_prefix%.refined.refined}"
    fi

    pids=()
    dx cat "$resources" | tar zx -C / & pids+=($!)
    dx download "$assembly" -o assembly.fa & pids+=($!)
    dx download "$reads" -o reads.bam & pids+=($!)
    dx cat "$novocraft_tarball" | tar zx & pids+=($!)
    mkdir gatk/
    dx cat "$gatk_tarball" | tar jx -C gatk/
    for pid in "${pids[@]}"; do wait $pid || exit $?; done
    export NOVOALIGN_PATH=/home/dnanexus/novocraft
    export GATK_PATH=/home/dnanexus/gatk

    # Novoalign reads to the assembly
    python viral-ngs/read_utils.py index_fasta_picard assembly.fa
    python viral-ngs/read_utils.py index_fasta_samtools assembly.fa
    novocraft/novoindex assembly.fa.nix assembly.fa
    samtools=viral-ngs/tools/build/samtools-0.1.19/samtools

    python viral-ngs/read_utils.py bam_to_fastq reads.bam reads.fa reads2.fa
    novocraft/novoalign $novoalign_options -f reads.fa reads2.fa \
                        -F STDFQ -o SAM -d assembly.fa.nix \
        | $samtools view -buS -q 1 - \
        | java -Xmx2g -jar viral-ngs/tools/build/picard-tools-1.126/picard.jar SortSam \
                      SO=coordinate VALIDATION_STRINGENCY=SILENT \
                      I=/dev/stdin O=reads.bam

    # set read group
    java -Xmx2g -jar viral-ngs/tools/build/picard-tools-1.126/picard.jar AddOrReplaceReadGroups \
                     VALIDATION_STRINGENCY=SILENT RGLB=UNKNOWN RGPL=ILLUMINA RGPU=UNKNOWN "RGSM=${name}" \
                     I=reads.bam O=reads.rg.bam

    # deduplicate
    python viral-ngs/read_utils.py mkdup_picard reads.rg.bam reads.rg.dedup.bam \
                                                --remove --picardOptions CREATE_INDEX=true

    # realign indels
    python viral-ngs/read_utils.py gatk_realign reads.rg.dedup.bam assembly.fa reads.realigned.dedup.bam

    # collect some statistics
    assembly_length=$(tail -n +1 assembly.fa | tr -d '\n' | wc -c)
    alignment_read_count=$($samtools view -c reads.rg.dedup.bam)
    alignment_base_count=$($samtools view reads.rg.dedup.bam | cut -f10 | tr -d '\n' | wc -c)
    mean_coverage_depth=$(expr $alignment_base_count / $assembly_length)
    genomecov=$(bedtools genomecov -ibam reads.rg.dedup.bam | dx upload -o "${name}.genomecov.txt" --brief -)

    # upload outputs
    dx-jobutil-add-output assembly_length $assembly_length
    dx-jobutil-add-output alignment_read_count $alignment_read_count
    dx-jobutil-add-output alignment_base_count $alignment_base_count
    dx-jobutil-add-output mean_coverage_depth $mean_coverage_depth
    dx-jobutil-add-output assembly_read_alignments --class=file \
        $(dx upload reads.realigned.dedup.bam --destination "${name}.mapped.bam" --brief)
    dx-jobutil-add-output alignment_genomecov "$genomecov"
    dx-jobutil-add-output final_assembly --class=file \
        $(dx upload assembly.fa --destination "${name}.fasta" --brief)
}