"""Entry point for the Windows distribution."""
import sys

if __name__ == "__main__":
    if sys.argv[1:2] == ["--verify-install"]:
        from release_check import main
    elif sys.argv[1:2] == ["--profile-render"]:
        from profile_stage8 import main
        del sys.argv[1]
    else:
        from game.__main__ import main
    main()
