import os
import sys
import json

from utils.db import get_connection_string


def main():
    try:
        conn = get_connection_string()
        print(conn)
    except:
        print("failed")


if __name__ == "__main__":
    main()
