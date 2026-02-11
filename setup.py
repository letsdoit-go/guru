"""Setup script with custom build command for proto compilation."""
from setuptools import setup
from setuptools.command.build_py import build_py
from pathlib import Path
from grpc_tools import protoc


class BuildWithProtos(build_py):
    """Custom build command that compiles protos before building."""

    def run(self):
        # Compile protos first
        self.compile_protos()
        # Then run normal build
        super().run()

    def compile_protos(self):
        """Compile proto files into the guru package."""
        project_root = Path(__file__).parent
        proto_dir = project_root / "src" / "guru" / "sensei-grpc-api"
        proto_file = "sensei_rpc.proto"
        proto_path = proto_dir / proto_file
        output_dir = project_root / "src" / "guru"

        if not proto_path.exists():
            raise RuntimeError(
                f"Proto file not found: {proto_path}\n"
                "Run: git submodule update --init"
            )

        print(f"Compiling {proto_file}...")
        result = protoc.main([
            'grpc_tools.protoc',
            f'--proto_path={proto_dir}',
            f'--python_out={output_dir}',
            f'--grpc_python_out={output_dir}',
            f'--pyi_out={output_dir}',
            str(proto_path)
        ])

        if result != 0:
            raise RuntimeError(f"Failed to compile {proto_file}")
        
        # Fix imports in generated gRPC file
        grpc_file = output_dir / "sensei_rpc_pb2_grpc.py"
        if grpc_file.exists():
            content = grpc_file.read_text()
            content = content.replace(
                "import sensei_rpc_pb2 as sensei__rpc__pb2",
                "from . import sensei_rpc_pb2 as sensei__rpc__pb2"
            )
            grpc_file.write_text(content)
            print(f"✓ Fixed imports in {grpc_file.name}")

        print(f"✓ Protos compiled to {output_dir}")


setup(
    cmdclass={
        'build_py': BuildWithProtos,
    }
)
