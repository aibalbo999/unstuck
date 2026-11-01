"""Pass only a checked read-only pipe to the original Popen-owned process."""
import inspect
import os
import sys

import pytest

from test_maintenance_owned_process import binding, module


def test_original_owned_process_can_inherit_one_admission_pipe(tmp_path):
    namespace = tmp_path / 'owner'
    namespace.mkdir(mode=0o700)
    controller = module().OwnedProcess(namespace, binding())
    reader, writer = os.pipe()
    try:
        child = "import os, sys; assert os.read(int(sys.argv[1]), 9) == b'permitted'; os.close(int(sys.argv[1]))"
        options = {'admission_fd': reader} if 'admission_fd' in inspect.signature(controller.start).parameters else {}
        controller.start([sys.executable, '-I', '-B', '-c', child, str(reader)], env={}, cwd=tmp_path, **options)
        os.close(reader)
        reader = None
        try:
            os.write(writer, b'permitted')
        except BrokenPipeError:
            pass  # The pre-fix child did not inherit the descriptor.
        result = controller.wait_for_exit(5)
        assert result['process_exited'] and result['returncode'] == 0, result
        assert result['admission_pipe_identity'] is not None
    finally:
        if reader is not None: os.close(reader)
        os.close(writer)
        if controller.process is not None: controller.process.wait(timeout=5)
        controller.close()


@pytest.mark.parametrize('kind', ['regular_file', 'write_end', 'named_public_fifo'])
def test_nonprivate_or_wrong_direction_admission_fd_never_launches(tmp_path, kind):
    adapter = module()
    namespace = tmp_path / 'owner'
    namespace.mkdir(mode=0o700)
    controller = adapter.OwnedProcess(namespace, binding())
    descriptors = []
    try:
        if kind == 'write_end':
            reader, fd = os.pipe()
            descriptors.extend((reader, fd))
        else:
            path = tmp_path / 'not-an-admission-pipe'
            if kind == 'regular_file':
                path.write_bytes(b'preserve')
                path.chmod(0o600)
            else:
                os.mkfifo(path, 0o660)
                path.chmod(0o660)
            fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
            descriptors.append(fd)
        with pytest.raises(adapter.ProcessUnavailable):
            controller.start([sys.executable, '-I', '-B', '-c', "raise AssertionError('Must not launch')"],
                env={}, cwd=tmp_path, admission_fd=fd)
        assert controller.process is None
        if kind == 'regular_file': assert path.read_bytes() == b'preserve'
        os.fstat(fd)  # Rejected foreign descriptors are not silently closed.
    finally:
        for fd in descriptors: os.close(fd)
        controller.close()
