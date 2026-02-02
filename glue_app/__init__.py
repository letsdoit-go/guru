"""
glue_app package initialization.

Compiles sensei_rpc.proto from sensei-grpc-api submodule and generates
Python modules in the project root directory for use across the application.
"""

import sys
import logging
from pathlib import Path
from grpc_tools import protoc

logger = logging.getLogger('INIT')


def _compile_proto():
    """
    Compile sensei_rpc.proto and place generated files in project root.

    This runs automatically when glue_app is imported. Generated files:
    - sensei_rpc_pb2.py
    - sensei_rpc_pb2_grpc.py
    - sensei_rpc_pb2.pyi
    """
    # Get paths
    glue_app_dir = Path(__file__).parent
    proto_dir = glue_app_dir / "sensei-grpc-api"
    proto_file = "sensei_rpc.proto"
    proto_path = proto_dir / proto_file

    # Output to project root (parent of glue_app)
    output_dir = glue_app_dir.parent

    if not proto_path.exists():
        raise RuntimeError(
            f"Proto file not found: {proto_path}\n"
            "Make sure the sensei-grpc-api submodule is initialized:\n"
            "  git submodule update --init --recursive"
        )

    # Compile the proto file
    logger.debug(f"Compiling {proto_file} from {proto_dir}")
    result = protoc.main([
        'grpc_tools.protoc',
        f'--proto_path={proto_dir}',
        f'--python_out={output_dir}',
        f'--grpc_python_out={output_dir}',
        f'--pyi_out={output_dir}',
        str(proto_path)
    ])

    if result != 0:
        raise RuntimeError(f"Failed to compile proto file: {proto_file}")

    logger.debug(f"Proto compiled successfully. Generated files in {output_dir}")

    # Ensure project root is in sys.path so modules can import the generated code
    if str(output_dir) not in sys.path:
        sys.path.insert(0, str(output_dir))


# Compile proto on import
_compile_proto()
