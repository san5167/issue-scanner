
import argparse
import json
import sys
import os
sys.path.append(os.path.dirname(sys.path[0]))
from reposca.prSca import PrSca
from reposca.commSca import CommSca


def commn():
    '''
    Calls issuescanner
    '''
    # start = time.time()
    parser = argparse.ArgumentParser()

    parser.add_argument("-m", "--method", required=True,
                        choices=['pr', 'repo', 'local'],
                        help="Select scan pr or repo")

    parser.add_argument("url", help="Specify the url/purl/http path to scan")

    parser.add_argument("--token", default="" ,required=False, help="Specify the token,Optional input" )

    args = parser.parse_args()
    method = args.method

    if method == 'pr':
        prSca = PrSca()
        result = prSca.doSca(args.url)
        jsonRe = json.dumps(result)
        print(jsonRe + "\n")
    elif method == 'repo':
        comSca = CommSca()
        result = comSca.runSca(args.url, args.token)
        jsonRe = json.dumps(result)
        print(jsonRe + "\n")
    else:
        comSca = CommSca()
        result = comSca.locSca(args.url)
        jsonRe = json.dumps(result)
        print(jsonRe + "\n")
    


if __name__ == '__main__':
    commn()