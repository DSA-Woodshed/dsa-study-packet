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
            if just deps-sync && source .venv/bin/activate; then
              echo ""
              echo "dsa-study-packet dev shell"
              echo "  python : $(python --version)"
              echo "  uv     : $(uv --version)"
              echo "  just   : $(just --version)"
              echo ""
              echo "Run 'just' to see available commands."
            else
              dsa_setup_status=$?
              printf 'Locked development setup failed; retry with just deps-sync.\n' >&2
              case $- in
                *i*) ;;
                *) exit "$dsa_setup_status" ;;
              esac
            fi
          '';

          env = {
            UV_PYTHON_PREFERENCE = "only-system";
            PYTHONDONTWRITEBYTECODE = "1";
          };
        };
      });
}
