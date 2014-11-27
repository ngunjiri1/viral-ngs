#!/usr/bin/env python
"""
Utilities for working with sequence reads, such as converting formats and
fixing mate pairs.
"""
from __future__ import division

__author__ = "irwin@broadinstitute.org"
__version__ = "PLACEHOLDER"
__date__ = "PLACEHOLDER"
__commands__ = []

import argparse, logging, os, tempfile, shutil
from Bio import SeqIO
import util.cmd, util.file
from util.file import mkstempfname
import tools.picard, tools.samtools

log = logging.getLogger(__name__)


# =======================
# ***  purge_unmated  ***
# =======================

def purge_unmated(inFastq1, inFastq2, outFastq1, outFastq2) :
    """Use mergeShuffledFastqSeqs to purge unmated reads, and put corresponding
       reads in the same order."""
    tempOutput = mkstempfname()
    mergeShuffledFastqSeqsPath = os.path.join(util.file.get_scripts_path(),
                                              'mergeShuffledFastqSeqs.pl')
    # The regular expression that follow says that the sequence identifiers
    # of corresponding sequences must be of the form SEQID/1 and SEQID/2
    cmdline = "{mergeShuffledFastqSeqsPath} -t -r '^@(\S+)/[1|2]$' " \
              "-f1 {inFastq1} -f2 {inFastq2} -o {tempOutput}".format(**locals())
    log.debug(cmdline)
    assert not os.system(cmdline)
    shutil.move(tempOutput + '.1.fastq', outFastq1)
    shutil.move(tempOutput + '.2.fastq', outFastq2)

def parser_purge_unmated() :
    parser = argparse.ArgumentParser(
        description='''Use mergeShuffledFastqSeqs to purge unmated reads, and
                       put corresponding reads in the same order.
                       Corresponding sequences must have sequence identifiers
                       of the form SEQID/1 and SEQID/2.
                    ''')
    parser.add_argument('inFastq1',
        help='Input fastq file; 1st end of paired-end reads.')
    parser.add_argument('inFastq2',
        help='Input fastq file; 2nd end of paired-end reads.')
    parser.add_argument('outFastq1',
        help='Output fastq file; 1st end of paired-end reads.')
    parser.add_argument('outFastq2',
        help='Output fastq file; 2nd end of paired-end reads.')
    util.cmd.common_args(parser, (('loglevel', None), ('version', None), ('tmpDir', None)))
    return parser

def main_purge_unmated(args) :
    inFastq1 = args.inFastq1
    inFastq2 = args.inFastq2
    outFastq1 = args.outFastq1
    outFastq2 = args.outFastq2
    purge_unmated(inFastq1, inFastq2, outFastq1, outFastq2)
    return 0

__commands__.append(('purge_unmated', main_purge_unmated,
                     parser_purge_unmated))

# =========================
# ***  fastq_to_fasta   ***
# =========================
def fastq_to_fasta(inFastq, outFasta) :
    'Convert from fastq format to fasta format.'
    'Warning: output reads might be split onto multiple lines.'
    
    # Do this with biopython rather than prinseq, because if the latter fails
    #    it doesn't return an error. (On the other hand, prinseq
    #    can guarantee that output lines are not split...)
    inFile  = util.file.open_or_gzopen(inFastq)
    outFile = util.file.open_or_gzopen(outFasta, 'w')
    for rec in SeqIO.parse(inFile, 'fastq') :
        SeqIO.write([rec], outFile, 'fasta')
    outFile.close()

def parser_fastq_to_fasta() :
    parser = argparse.ArgumentParser(
        description='Convert from fastq format to fasta format.')
    parser.add_argument('inFastq', help='Input fastq file.')
    parser.add_argument('outFasta', help='Output fasta file.')
    util.cmd.common_args(parser, (('loglevel', None), ('version', None), ('tmpDir', None)))
    return parser

def main_fastq_to_fasta(args) :
    inFastq = args.inFastq
    outFasta = args.outFasta
    fastq_to_fasta(inFastq, outFasta)
    return 0
__commands__.append(('fastq_to_fasta', main_fastq_to_fasta,
                     parser_fastq_to_fasta))

# =================================================
# ***  shared by bam_to_fastq and fastq_to_bam  ***
# =================================================

jvmMemDefault = '2g'

# =======================
# ***  bam_to_fastq   ***
# =======================
def bam_to_fastq(inBam, outFastq1, outFastq2, outHeader = None,
                 JVMmemory = jvmMemDefault, picardOptions = []) :
    'Convert a bam file to a pair of fastq paired-end read files and optional '\
    'text header.'
    
    SamToFastqPath = tools.picard.SamToFastqTool().install_and_get_path()
    tempdir = tempfile.gettempdir()
    samToFastqCmd = ('java -Xmx{JVMmemory}  -Djava.io.tmpdir={tempdir} '
                     '-jar {SamToFastqPath} '
                     'INPUT={inBam} '
                     'FASTQ={outFastq1} '
                     'SECOND_END_FASTQ={outFastq2} '
                     'VALIDATION_STRINGENCY=SILENT ' +
                     ' '.join(picardOptions)).format(**locals())
    log.debug(samToFastqCmd)
    assert not os.system(samToFastqCmd)
    
    if outHeader :
        samtoolsPath = tools.samtools.SamtoolsTool().install_and_get_path()
        dumpHeaderCmd = '{samtoolsPath} view -H {inBam} > {outHeader}'.format(
            **locals())
        log.debug(dumpHeaderCmd)
        assert not os.system(dumpHeaderCmd)

def parser_bam_to_fastq() :
    jvmMemDefault = '2g'
    parser = argparse.ArgumentParser(
        description='Convert a bam file to a pair of fastq paired-end '\
                    'read files and optional text header.')
    parser.add_argument('inBam', help='Input bam file.')
    parser.add_argument('outFastq1',
        help='Output fastq file; 1st end of paired-end reads.')
    parser.add_argument('outFastq2',
        help='Output fastq file; 2nd end of paired-end reads.')
    parser.add_argument('--outHeader',
        help='Optional text file name that will receive bam header.')
    parser.add_argument('--JVMmemory', default = jvmMemDefault,
        help='JVM virtual memory size (default: {})'.format(jvmMemDefault))
    parser.add_argument('--picardOptions', default = [], nargs='+',
        help='Optional arguments to picard\'s SamToFastq, OPTIONNAME=value ...')
    util.cmd.common_args(parser, (('loglevel', None), ('version', None), ('tmpDir', None)))
    return parser

def main_bam_to_fastq(args) :
    outFastq1 = args.outFastq1
    outFastq2 = args.outFastq2
    inBam = args.inBam
    outHeader = args.outHeader
    JVMmemory = args.JVMmemory
    picardOptions = args.picardOptions
    bam_to_fastq(inBam, outFastq1, outFastq2, outHeader, JVMmemory,
                 picardOptions)
    return 0

__commands__.append(('bam_to_fastq', main_bam_to_fastq,
                     parser_bam_to_fastq))

# =======================
# ***  fastq_to_bam   ***
# =======================

def fastq_to_bam(inFastq1, inFastq2, outBam, sampleName = None, header = None,
                 JVMmemory = jvmMemDefault, picardOptions = []) :
    'Convert a pair of fastq paired-end read files and optional text header ' \
    'to a single bam file.'
    
    FastqToSamPath = tools.picard.FastqToSamTool().install_and_get_path()
    if header :
        fastqToSamOut = mkstempfname()
    else :
        fastqToSamOut = outBam
    tempdir = tempfile.gettempdir()
    if sampleName == None :
        sampleName = 'Dummy' # Will get overwritten by rehead command
    if header :
        # With the header option, rehead will be called after FastqToSam.
        # This will invalidate any md5 file, which would be a slow to construct
        # on our own, so just disallow and let the caller run md5sum if desired.
        assert not any(opt.lower() == 'CREATE_MD5_FILE=True'.lower()
                       for opt in picardOptions), \
            'CREATE_MD5_FILE is not allowed with --header.'
    fastqToSamCmd = ('java -Xmx{JVMmemory} -Djava.io.tmpdir={tempdir} '
                     '-jar {FastqToSamPath} '
                     'FASTQ={inFastq1} FASTQ2={inFastq2} '
                     'OUTPUT={fastqToSamOut} '
                     'SAMPLE_NAME={sampleName} ' +
                     ' '.join(picardOptions)).format(**locals())
    log.debug(fastqToSamCmd)
    assert not os.system(fastqToSamCmd)
    if header :
        samtoolsPath = tools.samtools.SamtoolsTool().install_and_get_path()
        reheadCmd = '{samtoolsPath} reheader {header} {fastqToSamOut} >' \
                    '{outBam}'.format(**locals())
        log.debug(reheadCmd)
        assert not os.system(reheadCmd)

def parser_fastq_to_bam() :
    parser = argparse.ArgumentParser(
        description='Convert a pair of fastq paired-end read files and '
                    'optional text header to a single bam file.')
    parser.add_argument('inFastq1',
        help='Input fastq file; 1st end of paired-end reads.')
    parser.add_argument('inFastq2',
        help='Input fastq file; 2nd end of paired-end reads.')
    parser.add_argument('outBam', help='Output bam file.')
    headerGroup = parser.add_mutually_exclusive_group(required = True)
    headerGroup.add_argument('--sampleName',
        help='Sample name to insert into the read group header.')
    headerGroup.add_argument('--header',
        help='Optional text file containing header.')
    parser.add_argument('--JVMmemory', default = jvmMemDefault,
        help='JVM virtual memory size (default: {})'.format(jvmMemDefault))
    parser.add_argument('--picardOptions', default = [], nargs='+',
        help='''Optional arguments to picard\'s FastqToSam,
                OPTIONNAME=value ...  Note that header-related options will be 
                overwritten by HEADER if present.''')
    util.cmd.common_args(parser, (('loglevel', None), ('version', None), ('tmpDir', None)))
    return parser

def main_fastq_to_bam(args) :
    inFastq1 = args.inFastq1
    inFastq2 = args.inFastq2
    outBam = args.outBam
    sampleName = args.sampleName
    header = args.header
    JVMmemory = args.JVMmemory
    picardOptions = args.picardOptions
    fastq_to_bam(inFastq1, inFastq2, outBam, sampleName, header, JVMmemory,
                 picardOptions)
    return 0

__commands__.append(('fastq_to_bam', main_fastq_to_bam,
                     parser_fastq_to_bam))


# ======================
# ***  split_reads   ***
# ======================
defaultSuffixLen = 2
defaultMaxReads = 1000
defaultFormat = 'fastq'

def split_reads(inFileName, outPrefix, maxReads = None, numChunks = None,
                suffixLen = defaultSuffixLen, format = defaultFormat) :
    '''Split fasta or fastq file into chunks of maxReads reads or into 
           numChunks chunks named outPrefixaa, outPrefixab, etc.
       If both maxReads and numChunks are None, use defaultMaxReads.
       The number of characters in file names after outPrefix is suffixLen;
            if not specified, use defaultSuffixLen.
       Format can be 'fastq' or 'fasta'.
    '''
    def index_to_suffix(index, suffixLen) :
        'Convert an integer index into a suffix aaa, aab, aac, ...'
        suffix = ''
        while index > 0 :
            suffix = chr(ord('a') + index % 26) + suffix
            index //= 26
        assert len(suffix) <= suffixLen
        suffix = 'a' * (suffixLen - len(suffix)) + suffix
        return suffix
    
    if maxReads == None :
        if numChunks == None :
            maxReads = defaultMaxReads
        else :
            inFile  = util.file.open_or_gzopen(inFileName)
            totalReadCount = 0
            for rec in SeqIO.parse(inFile, format) :
                totalReadCount += 1
            maxReads = int(totalReadCount / numChunks + 0.5)
            inFile.close()

    inFile  = util.file.open_or_gzopen(inFileName)
    readsWritten = 0
    curIndex = 0
    outFile = None
    for rec in SeqIO.parse(inFile, format) :
        if outFile == None :
            outFileName = outPrefix + index_to_suffix(curIndex, suffixLen)
            outFile = util.file.open_or_gzopen(outFileName, 'w')
        SeqIO.write([rec], outFile, format)
        readsWritten += 1
        if readsWritten == maxReads :
            outFile.close()
            outFile = None
            readsWritten = 0
            curIndex += 1
    if outFile != None :
        outFile.close()

def parser_split_reads() :
    parser = argparse.ArgumentParser(
        description='Split a fastq or fasta file into chunks.')
    parser.add_argument('inFile', help='Input fastq or fasta file.')
    parser.add_argument('outPrefix',
        help='Output files will be named ${outPrefix}aa, ${outPrefix}ab...')
    group = parser.add_mutually_exclusive_group(required = False)
    group.add_argument('--maxReads', type = int,
        help = 'Maximum number of reads per chunk (default {:d} if neither '\
               'maxReads nor numChunks is specified).'.format(defaultMaxReads))
    group.add_argument('--numChunks', type = int,
        help = 'Number of output files, if maxReads is not specified.')
    parser.add_argument('--suffixLen', type = int, default = defaultSuffixLen,
        help = 'Number of characters to append to outputPrefix for each '\
               'output file (default {}). Number of files must not exceed '\
               '26^SUFFIXLEN.'.format(defaultSuffixLen))
    parser.add_argument('--format', choices = ['fastq', 'fasta'],
        default = defaultFormat,
        help='Input fastq or fasta file (default {}).'.format(defaultFormat))
    return parser

def main_split_reads(args) :
    split_reads(args.inFile, args.outPrefix, args.maxReads, args.numChunks,
                args.suffixLen, args.format)
    return 0
__commands__.append(('split_reads', main_split_reads,
                     parser_split_reads))

# =======================

if __name__ == '__main__':
    util.cmd.main_argparse(__commands__, __doc__)