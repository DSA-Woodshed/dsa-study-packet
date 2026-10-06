{
  description = "DSA and technical interview study environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
        python = pkgs.python314;
      in
      {
        devShells.default = pkgs.mkShell {
          name = "dsa-study-packet";

          packages = [
            python
            pkgs.uv
            pkgs.just
            pkgs.git-cliff
            pkgs.pandoc
            pkgs.tectonic
            pkgs.entr
            pkgs.watchexec
          ];

          shellHook = ''
            # Create venv if it doesn't exist
            if [ ! -d .venv ]; then
              echo "Creating virtual environment..."
              uv venv --python ${python}/bin/python
            fi

            # Activate venv
            source .venv/bin/activate

            # Sync dev deps
            uv sync --all-extras 2>/dev/null || uv pip install -e ".[dev]"

            echo ""
            echo "dsa-study-packet dev shell"
            echo "  python : $(python --version)"
            echo "  uv     : $(uv --version)"
            echo "  just   : $(just --version)"
            echo ""
            echo "Run 'just' to see available commands."
          '';

          env = {
            UV_PYTHON_PREFERENCE = "only-system";
            PYTHONDONTWRITEBYTECODE = "1";
          };
        };
      });
}
