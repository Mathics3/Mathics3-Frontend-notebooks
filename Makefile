# A GNU Makefile to run various tasks - compatibility for us old-timers.

# Note: This makefile include remake-style target comments.
# These comments before the targets start with #:
# remake --tasks to shows the targets and the comments

.PHONY: all \
   ChangeLog-without-corrections \
   console \
   dist \
   lab \
   notebook \
   register-kernel \
   rmChangeLog

GIT2CL ?= admin-tools/git2cl
PYTHON3 ?= python3

# Default options
o = --notebook-dir=$(HOME)/Jupyter-notebooks

#: Make distribution: wheels and tarball
dist:
	./admin-tools/make-dist.sh

#: Run a Jupyter lab; the more modern IDE
lab:
	jupyter lab --kernel=mathics3-extension-ipykernel $o

#: List all of the Jupyter Kernels installed
list-kernels:
	jupyter kernelspec list

#: Run a Jupyter notebook; the classic single-instance interface
notebook:
	jupyter notebook $o

#: Run a Jupyter console; for debugging.
console:
	jupyter console --kernel=mathics3-extension-ipykernel

#: Register a mathics3 Jupyter kernel
register-kernel:
	$(PYTHON3) -m mathics3_kernel.frontend.install_kernel

#: Remove ChangeLog
rmChangeLog:
	$(RM) ChangeLog || true

#: Create ChangeLog from version control without corrections
ChangeLog-without-corrections:
	git log --pretty --numstat --summary | $(GIT2CL) >ChangeLog

#: Create a ChangeLog from git via git log and git2cl
ChangeLog: rmChangeLog ChangeLog-without-corrections
	patch ChangeLog < ChangeLog-spell-corrected.diff
