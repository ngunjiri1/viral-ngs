#!/bin/bash

main() {
    set -e -x -o pipefail

    dx cat "$resources" | zcat | tar x -C / &
    dx download "$raw_assembly" -o raw_assembly.fa &
    dx cat "$reads" | zcat > reads.fa &
    dx cat "$reads2" | zcat > reads2.fa &
    dx download "$reference_genome" -o reference_genome.fa
    wait

    # symlink R in the path hardcoded into contigMerger.pl
    mkdir -p /broad/software/free/Linux/redhat_5_x86_64/pkgs/r_2.15.1/bin
    ln -s "$(which R)" /broad/software/free/Linux/redhat_5_x86_64/pkgs/r_2.15.1/bin/R

    # run V-FAT scripts to orient & merge contigs
    mkdir foo/
    viral-ngs/tools/scripts/vfat/orientContig.pl raw_assembly.fa reference_genome.fa foo/bar
    viral-ngs/tools/scripts/vfat/contigMerger.pl foo/bar_orientedContigs reference_genome.fa -readfq reads.fa -readfq2 reads2.fa -fakequals 30 foo/bar
    ls -tl foo

    # check assembly quality thresholds
    python viral-ngs/assembly.py filter_short_seqs foo/bar_assembly.fa "$min_length" "$min_unambig" assembly-vfat.fa
    if ! test -s assembly-vfat.fa; then
        dx-jobutil-report-error "The assembly failed quality thresholds (length >= ${min_length}, non-N proportion >= ${min_unambig})" AppError
        exit 1
    fi

    # upload outputs
    dx-jobutil-add-output assembly --class=file \
    	$(dx upload assembly-vfat.fa --destination "${raw_assembly_prefix}.finished.fasta" --brief)
    dx-jobutil-add-output contigsMap --class=file \
    	$(dx upload foo/bar_contigsMap.pdf --destination "${raw_assembly_prefix}.finished.contigsMap.pdf" --brief)
}