"""Fresh interpreter for optional CUDA packages; no widgets, VTK or serial access."""
from pathlib import Path
import sys


def serve(target):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    sys.path.insert(0, str(Path(target).resolve()))
    from acousticstudio.cuda_protocol import read_message, write_message
    wire = sys.stdout.buffer
    sys.stdout = sys.stderr  # Library diagnostics cannot corrupt the binary pipe.
    torch = None
    while True:
        try:
            operation, arguments = read_message(sys.stdin.buffer)
        except EOFError:
            return
        try:
            if torch is None:
                import torch
            if operation == 'probe':
                available = bool(torch.cuda.is_available())
                if available:
                    # Also check a real complex128 kernel, beyond package/device presence.
                    value = torch.ones((1, 1), dtype=torch.complex128, device='cuda')
                    value = value @ value
                    torch.cuda.synchronize()
                result = dict(torch_version=str(torch.__version__), torch_cuda_build=torch.version.cuda,
                              cuda_available=available, cuda_device=torch.cuda.get_device_name() if available else None,
                              cuda_error=None if available else '별도 PyTorch 런타임이 CUDA 장치를 사용할 수 없습니다.',
                              torch_file=str(Path(torch.__file__).resolve()))
            elif operation == 'matvec':
                matrix, weights = arguments
                result = (torch.as_tensor(matrix, dtype=torch.complex128, device='cuda') @
                          torch.as_tensor(weights, dtype=torch.complex128, device='cuda')).cpu().numpy()
            elif operation in ('phases', 'field_slice'):
                from acousticstudio import sonic_wrapper
                if not sonic_wrapper._has_cuda:
                    raise RuntimeError('CUDA 계산 프로세스가 GPU를 사용할 수 없습니다.')
                function = (sonic_wrapper.calculate_phases_gpu if operation == 'phases'
                            else sonic_wrapper.calculate_field_slice_gpu)
                result = function(*arguments)
            else:
                raise ValueError('지원하지 않는 CUDA 계산 요청입니다.')
            response = dict(ok=True, value=result)
        except Exception as exc:
            response = dict(ok=False, error=str(exc))
        write_message(wire, response)


if __name__ == '__main__':
    serve(sys.argv[1])
