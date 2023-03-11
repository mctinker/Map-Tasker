from maptasker.src import mapit


def main():
    """
    Kick off the main program: mapit.py
    """
    return_code = mapit.mapit_all()
    exit(return_code)


main()
