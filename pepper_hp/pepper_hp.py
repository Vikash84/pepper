import argparse
import sys
import torch
from datetime import datetime
from pepper.version import __version__
from pepper_hp.modules.python.MakeImages import make_images
from pepper_hp.modules.python.RunInference import run_inference
from pepper_hp.modules.python.FindCandidates import process_candidates
from pepper_hp.modules.python.MergeVCFsWithSimplify import haploid2diploid
# from pepper_hp.modules.python.MergeVCFs import haploid2diploid
from pepper_hp.modules.python.CallVariant import call_variant

def boolean_string(s):
    """
    https://stackoverflow.com/questions/44561722/why-in-argparse-a-true-is-always-true
    :param s: string holding boolean value
    :return:
    """
    if s.lower() not in {'false', 'true', '1', 't', '0', 'f'}:
        raise ValueError('Not a valid boolean string')
    return s.lower() == 'true' or s.lower() == 't' or s.lower() == '1'


def add_call_variant_arguments(parser):
    """
    Add arguments to a parser for sub-command "polish"
    :param parser: argeparse object
    :return:
    """
    parser.add_argument(
        "-b",
        "--bam",
        type=str,
        required=True,
        help="BAM file containing mapping between reads and the draft assembly."
    )
    parser.add_argument(
        "-f",
        "--fasta",
        type=str,
        required=True,
        help="FASTA file containing the draft assembly."
    )
    parser.add_argument(
        "-m",
        "--model_path",
        type=str,
        required=True,
        help="Path to a trained model."
    )
    parser.add_argument(
        "-o",
        "--output_dir",
        type=str,
        required=True,
        help="Path to output directory."
    )
    parser.add_argument(
        "-s",
        "--sample_name",
        type=str,
        default="SAMPLE",
        required=False,
        help="Name of the sample. Default: SAMPLE"
    )
    parser.add_argument(
        "-t",
        "--threads",
        required=True,
        type=int,
        help="Number of threads to use."
    )
    parser.add_argument(
        "-r",
        "--region",
        type=str,
        help="Region in [contig_name:start-end] format"
    )
    parser.add_argument(
        "-bs",
        "--batch_size",
        type=int,
        required=False,
        default=128,
        help="Batch size for testing, default is 128. Suggested values: 256/512/1024."
    )
    parser.add_argument(
        "-g",
        "--gpu",
        default=False,
        action='store_true',
        help="If set then PyTorch will use GPUs for inference. CUDA required."
    )
    parser.add_argument(
        "-per_gpu",
        "--callers_per_gpu",
        type=int,
        required=False,
        default=4,
        help="Number of callers to initialize per GPU, on a 11GB GPU, you can go up to 10. Default is 4."
    )
    parser.add_argument(
        "-d_ids",
        "--device_ids",
        type=str,
        required=False,
        default=None,
        help="List of gpu device ids to use for inference. Only used in distributed setting.\n"
             "Example usage: --device_ids 0,1,2 (this will create three callers in id 'cuda:0, cuda:1 and cuda:2'\n"
             "If none then it will use all available devices."
    )
    parser.add_argument(
        "-w",
        "--num_workers",
        type=int,
        required=False,
        default=4,
        help="Number of workers for loading images. Default is 4."
    )
    return parser


def add_make_images_arguments(parser):
    """
    Add arguments to a parser for sub-command "make_images"
    :param parser: argeparse object
    :return:
    """
    parser.add_argument(
        "-b",
        "--bam",
        type=str,
        required=True,
        help="BAM file containing mapping between reads and the draft assembly."
    )
    parser.add_argument(
        "-f",
        "--fasta",
        type=str,
        required=True,
        help="FASTA file containing the draft assembly."
    )
    parser.add_argument(
        "-hp",
        "--hp_tag",
        type=int,
        required=True,
        default=None,
        help="Haplotype tag to process from the BAM file."
    )
    parser.add_argument(
        "-t",
        "--threads",
        required=True,
        type=int,
        help="Number of threads to use. Default is 5."
    )
    parser.add_argument(
        "-r",
        "--region",
        type=str,
        help="Region in [chr_name:start-end] format"
    )
    parser.add_argument(
        "-o",
        "--output_dir",
        type=str,
        default="pepper_hp_output/",
        help="Path to output directory, if it doesn't exist it will be created."
    )
    return parser


def add_run_inference_arguments(parser):
    """
    Add arguments to a parser for sub-command "call_consensus"
    :param parser: argeparse object
    :return:
    """
    parser.add_argument(
        "-i",
        "--image_dir",
        type=str,
        required=True,
        help="Path to directory containing all HDF5 images."
    )
    parser.add_argument(
        "-m",
        "--model_path",
        type=str,
        required=True,
        help="Path to a trained model."
    )
    parser.add_argument(
        "-o",
        "--output_dir",
        type=str,
        required=True,
        default='output',
        help="Path to the output directory."
    )
    parser.add_argument(
        "-bs",
        "--batch_size",
        type=int,
        required=False,
        default=128,
        help="Batch size for testing, default is 100. Suggested values: 256/512/1024. Default is 128."
    )
    parser.add_argument(
        "-g",
        "--gpu",
        default=False,
        action='store_true',
        help="If set then PyTorch will use GPUs for inference. CUDA required. Default is False."
    )
    parser.add_argument(
        "-d_ids",
        "--device_ids",
        type=str,
        required=False,
        default=None,
        help="List of gpu device ids to use for inference. Only used in distributed setting.\n"
             "Example usage: --device_ids 0,1,2 (this will create three callers in id 'cuda:0, cuda:1 and cuda:2'\n"
             "If none then it will use all available devices. Default is None."
    )
    parser.add_argument(
        "-per_gpu",
        "--callers_per_gpu",
        type=int,
        required=False,
        default=4,
        help="Number of callers to initialize per GPU, on a 11GB GPU, you can go up to 10. Default is 4."
    )
    parser.add_argument(
        "-w",
        "--num_workers",
        type=int,
        required=False,
        default=4,
        help="Number of workers for loading images. Default is 4."
    )
    parser.add_argument(
        "-t",
        "--threads",
        type=int,
        required=False,
        default=8,
        help="Total threads. Default is 8."
    )
    return parser


def add_find_candidates_arguments(parser):
    """
    Add arguments to a parser for sub-command "stitch"
    :param parser: argeparse object
    :return:
    """
    parser.add_argument(
        "-i",
        "--input_dir",
        type=str,
        required=True,
        help="Path to directory containing HDF files."
    )
    parser.add_argument(
        "-r",
        "--input_reference",
        type=str,
        required=True,
        help="Input reference/assembly file."
    )
    parser.add_argument(
        "-s",
        "--sample_name",
        type=str,
        default="SAMPLE",
        required=False,
        help="Name of the sample. Default: SAMPLE"
    )
    parser.add_argument(
        "-o",
        "--output_dir",
        type=str,
        required=True,
        help="Path to output directory."
    )
    parser.add_argument(
        "-t",
        "--threads",
        required=True,
        type=int,
        help="Number of threads."
    )
    return parser


def add_merge_vcf_arguments(parser):
    parser.add_argument(
        "-v1",
        "--vcf_h1",
        type=str,
        required=True,
        help="VCF of haplotype 1."
    )
    parser.add_argument(
        "-v2",
        "--vcf_h2",
        type=str,
        required=True,
        help="VCF of haplotype 1."
    )
    parser.add_argument(
        "-r",
        "--reference",
        type=str,
        required=True,
        help="FASTA file containing the reference assembly."
    )
    parser.add_argument(
        "-o",
        "--output_dir",
        type=str,
        default="candidate_finder_output/",
        help="Path to output directory, if it doesn't exist it will be created."
    )
    return parser


def main():
    """
    Main interface for PEPPER. The submodules supported as of now are these:
    1) Make images
    2) Call consensus
    3) Stitch
    """
    parser = argparse.ArgumentParser(description="PEPPER is a RNN based polisher for polishing ONT-based assemblies. "
                                                 "It works in three steps:\n"
                                                 "1) make_images: This module takes alignment file and coverts them"
                                                 "to HDF5 files containing summary statistics.\n"
                                                 "2) run_inference: This module takes the summary images and a"
                                                 "trained neural network and generates predictions per base.\n"
                                                 "3) find_snps: This module takes the inference files as input and "
                                                 "finds possible SNP sites.\n",
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument(
        "--version",
        default=False,
        action='store_true',
        help="Show version."
    )

    subparsers = parser.add_subparsers(dest='sub_command')
    subparsers.required = True

    parser_call_variant = subparsers.add_parser('call_variant', help="Run the variant calling pipeline. This will run "
                                                                     "make images-> inference -> find_candidates one after another.\n"
                                                                     "The outputs of each step can be run separately using\n"
                                                                     "the appropriate sub-command.")
    add_call_variant_arguments(parser_call_variant)

    parser_make_images = subparsers.add_parser('make_images', help="Generate images that encode summary statistics "
                                                                   "of reads aligned to an assembly.")
    add_make_images_arguments(parser_make_images)

    parser_run_inference = subparsers.add_parser('run_inference', help="Perform inference on generated images using "
                                                                       "a trained model.")
    add_run_inference_arguments(parser_run_inference)

    parser_find_candidates = subparsers.add_parser('find_candidates', help="Find candidate variants.")
    add_find_candidates_arguments(parser_find_candidates)

    parser_find_candidates = subparsers.add_parser('merge_vcf', help="Merge haplotype 1 and 2 variants to generate a phased VCF.")
    add_merge_vcf_arguments(parser_find_candidates)

    # parser_download_model = subparsers.add_parser('download_models', help="Download available models.")
    # add_download_models_arguments(parser_download_model)

    parser_torch_stat = subparsers.add_parser('torch_stat', help="See PyTorch configuration.")
    parser_torch_stat = subparsers.add_parser('version', help="Show program version.")

    FLAGS, unparsed = parser.parse_known_args()

    if FLAGS.sub_command == 'call_variant':
        sys.stderr.write("[" + str(datetime.now().strftime('%m-%d-%Y %H:%M:%S')) + "] INFO: CALL VARIANT MODULE SELECTED\n")
        call_variant(FLAGS.bam,
                     FLAGS.fasta,
                     FLAGS.output_dir,
                     FLAGS.threads,
                     FLAGS.region,
                     FLAGS.model_path,
                     FLAGS.batch_size,
                     FLAGS.gpu,
                     FLAGS.callers_per_gpu,
                     FLAGS.device_ids,
                     FLAGS.num_workers,
                     FLAGS.sample_name)

    elif FLAGS.sub_command == 'make_images':
        sys.stderr.write("[" + str(datetime.now().strftime('%m-%d-%Y %H:%M:%S')) + "] INFO: MAKE IMAGE MODULE SELECTED.\n")
        make_images(FLAGS.bam,
                    FLAGS.fasta,
                    FLAGS.region,
                    FLAGS.output_dir,
                    FLAGS.hp_tag,
                    FLAGS.threads)

    elif FLAGS.sub_command == 'run_inference':
        sys.stderr.write("[" + str(datetime.now().strftime('%m-%d-%Y %H:%M:%S')) + "] INFO: RUN INFERENCE MODULE SELECTED.\n")
        run_inference(FLAGS.image_dir,
                      FLAGS.model_path,
                      FLAGS.batch_size,
                      FLAGS.num_workers,
                      FLAGS.output_dir,
                      FLAGS.device_ids,
                      FLAGS.callers_per_gpu,
                      FLAGS.gpu,
                      FLAGS.threads)

    elif FLAGS.sub_command == 'find_candidates':
        sys.stderr.write("[" + str(datetime.now().strftime('%m-%d-%Y %H:%M:%S')) + "] INFO: FIND CANDIDATE MODULE SELECTED\n")
        process_candidates(FLAGS.input_dir,
                           FLAGS.input_reference,
                           FLAGS.sample_name,
                           FLAGS.output_dir,
                           FLAGS.threads)

    elif FLAGS.sub_command == 'merge_vcf':
        sys.stderr.write("[" + str(datetime.now().strftime('%m-%d-%Y %H:%M:%S')) + "] INFO: MERGE VCFs MODULE SELECTED\n")
        haploid2diploid(FLAGS.vcf_h1,
                        FLAGS.vcf_h2,
                        FLAGS.reference,
                        FLAGS.output_dir,
                        adjacent=False,
                        discard_phase=False)

    elif FLAGS.sub_command == 'torch_stat':
        sys.stderr.write("TORCH VERSION: " + str(torch.__version__) + "\n\n")
        sys.stderr.write("PARALLEL CONFIG:\n")
        print(torch.__config__.parallel_info())
        sys.stderr.write("BUILD CONFIG:\n")
        print(*torch.__config__.show().split("\n"), sep="\n")

        sys.stderr.write("CUDA AVAILABLE: " + str(torch.cuda.is_available()) + "\n")
        sys.stderr.write("GPU DEVICES: " + str(torch.cuda.device_count()) + "\n")

    elif FLAGS.version is True:
        print("PEPPER VERSION: ", __version__)
    else:
        sys.stderr.write("ERROR: NO SUBCOMMAND SELECTED. PLEASE SELECT ONE OF THE AVAIABLE SUB-COMMANDS.\n")
        parser.print_help()


if __name__ == '__main__':
    main()
