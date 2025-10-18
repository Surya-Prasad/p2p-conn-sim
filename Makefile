# Makefile for P2P File Sharing Simulation

# --- Configuration ---

# Define the virtual environment directory (from .gitignore)
VENV_DIR = env-p2p-comm-sim

# Define the Python interpreter within the virtual environment
PYTHON = $(VENV_DIR)/bin/python
PIP = $(VENV_DIR)/bin/pip

# --- Default Peer Configuration ---
# You can override these from the command line, e.g.:
# make run-seed PORT=8001 SHARE_DIR=./my-files

# Default values for the seeder
PORT_SEED ?= 8001
SHARE_DIR_SEED ?= ./seeding-directory

# Default values for the leecher
# Note: The leecher's "share-dir" is where completed files are saved.
PORT_LEECH ?= 8002
SHARE_DIR_LEECH ?= ./complete-files

# --- Targets ---

# Phony targets do not correspond to file names
.PHONY: all install run-server run-seed run-leech clean

# Default target to run when 'make' is called without arguments
all: install

# Target to set up the environment
# Creates the virtual env and installs requirements
$(VENV_DIR)/bin/activate: requirements.txt
	@echo "Creating virtual environment in $(VENV_DIR)..."
	python3 -m venv $(VENV_DIR)
	@echo "Installing dependencies from requirements.txt..."
	$(PIP) install -r requirements.txt
	@touch $(VENV_DIR)/bin/activate

# 'install' is an alias for the virtual env setup
install: $(VENV_DIR)/bin/activate

# Target to run the P2P server
run-server: install
	@echo "Starting P2P server..."
	$(PYTHON) p2p-server/main.py

# Target to run a peer in seed mode
run-seed: install
	@echo "Starting P2P peer in SEED mode..."
	@echo "  Port: $(PORT_SEED)"
	@echo "  Share Directory: $(SHARE_DIR_SEED)"
	$(PYTHON) p2p-peer/main.py --mode seed --share-dir $(SHARE_DIR_SEED) --peer-port $(PORT_SEED)

# Target to run a peer in leech mode
run-leech: install
	@echo "Starting P2P peer in LEECH mode..."
	@echo "  Port: $(PORT_LEECH)"
	@echo "  Download Directory: $(SHARE_DIR_LEECH)"
	$(PYTHON) p2p-peer/main.py --mode leech --share-dir $(SHARE_DIR_LEECH) --peer-port $(PORT_LEECH)

# Target to clean up the project directory
clean:
	@echo "Cleaning up project..."
	# Remove virtual environment
	rm -rf $(VENV_DIR)
	# Remove Python cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.py[co]" -delete
	# Remove downloaded pieces (based on .gitignore)
	find . -type f -name "*.piece" -delete
	# Remove other items from .gitignore
	rm -rf build/ dist/ *.egg-info/ .eggs/
	rm -f *.log
	rm -rf htmlcov/ .coverage .cache