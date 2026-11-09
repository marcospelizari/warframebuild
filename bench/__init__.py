"""Step 4.5 performance spike (#19); see README.md. Not part of app/.

One BLAS thread per process: the matrices are tiny, and BLAS threads in every pool worker
oversubscribe the CPU (measured: 12 workers slower than 6 without this).
"""

import os

for _var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_var, "1")
