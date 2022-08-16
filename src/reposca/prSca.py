# -*- coding: utf-8 -*-
import logging
import os
import shlex
import stat
import subprocess
import time
from requests import head
import urllib3
import json
import jsonpath
from pyrpm.spec import Spec

from reposca.makeRepoCsv import checkNotice, checkRepoLicense
from reposca.repoDb import RepoDb
from reposca.takeRepoSca import cleanTemp
from reposca.licenseCheck import LicenseCheck
from util.popUtil import popKill
from util.extractUtil import extractCode
from util.formateUtil import formateUrl
from util.catchUtil import catch_error
from util.postOrdered import infixToPostfix

from git.repo import Repo

ACCESS_TOKEN = '694b8482b84b3704c70bceef66e87606'
GIT_URL = 'https://gitee.com'
SOURTH_PATH = '/home/giteeFile'
logging.getLogger().setLevel(logging.INFO)

class PrSca(object):

    def __init__(self):
        self._current_dir_ = os.path.dirname(os.path.abspath(__file__))

    @catch_error
    def doSca(self, url):
        try:
            urlList = url.split("/")
            self._owner_ = urlList[3]
            self._repo_ = urlList[4]
            self._num_ = urlList[6]
            self._branch_ = 'pr_' + self._num_
            gitUrl = GIT_URL + '/' + self._owner_ + '/' + self._repo_ + '.git'
            fetchUrl = 'pull/' + self._num_ + '/head:pr_' + self._num_
            timestamp = int(time.time())

            # 创建临时文件
            temFileSrc = self._current_dir_+'/tempSrc'
            temFileSrc = formateUrl(temFileSrc)

            if os.path.exists(temFileSrc) is False:
                os.makedirs(temFileSrc)

            self._repoSrc_ = SOURTH_PATH + '/'+self._owner_ + '/' + self._repo_
            self._anlyzeSrc_ = SOURTH_PATH + '/'+self._owner_
            delSrc = ''
            self._file_ = 'sourth'
            if os.path.exists(self._repoSrc_) is False:
                self._file_ = 'temp'
                self._repoSrc_ = temFileSrc + '/'+self._owner_ + '/' + str(timestamp) + '/' + self._repo_
                self._anlyzeSrc_ = temFileSrc + '/' + self._owner_ + '/' + str(timestamp)
                delSrc = temFileSrc + '/'+self._owner_ + '/' + str(timestamp)
                if os.path.exists(self._repoSrc_) is False:
                    os.makedirs(self._repoSrc_)

            repo = Repo.init(path=self._repoSrc_)
            self._gitRepo_ = repo
            self._git_ = repo.git

            logging.info("=============Start fetch repo==============")
            # 拉取pr
            if self._file_ == 'sourth':
                remote = self._gitRepo_.remote()
            else:
                remote = self._gitRepo_.create_remote('origin', gitUrl)
            remote.fetch(fetchUrl, depth=1)
            # 切换分支
            self._git_.checkout(self._branch_)
            logging.info("=============End fetch repo==============")

            # 扫描pr文件
            scaJson = self.getPrSca()
            scaResult = self.getScaAnalyze(scaJson)
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.exception("Error on %s" % (e))
        finally:
            # 清理临时文件
            if delSrc != '':
                try:
                    cleanTemp(delSrc)
                    os.chmod(delSrc, stat.S_IWUSR)
                    os.rmdir(delSrc)
                except:
                    pass
            return scaResult

    @catch_error
    def getPrBranch(self):
        '''
        :param owner: 仓库所属空间地址(企业、组织或个人的地址path)
        :param repo: 仓库路径(path)
        :param number: 	第几个PR，即本仓库PR的序数
        :return:head,base
        '''
        repoStr = "Flag"
        apiJson = ''
        http = urllib3.PoolManager()
        url = 'https://gitee.com/api/v5/repos/' + self._owner_ + '/' + \
            self._repo_ + '/pulls/' + self._num_ + '?access_token='+ACCESS_TOKEN
        response = http.request('GET', url)
        resStatus = response.status

        while resStatus == '403':
            return 403, 403

        while resStatus == '502':
            return 502, 502

        repoStr = response.data.decode('utf-8')
        apiJson = json.loads(repoStr)

        head = jsonpath.jsonpath(apiJson, '$.head.ref')
        base = jsonpath.jsonpath(apiJson, '$.base.ref')

        return head, base

    @catch_error
    def getPrSca(self):
        '''
        :param repoSrc: 扫描项目路径
        :param pathList: 扫描文件路径List
        :return:扫描结果json
        '''
        try:
            temJsonSrc = self._current_dir_+'/tempJson'
            temJsonSrc = formateUrl(temJsonSrc)
            if os.path.exists(temJsonSrc) is False:
                os.makedirs(temJsonSrc)

            timestamp = int(time.time())
            tempJson = temJsonSrc + '/' + self._repo_+str(timestamp)+'.txt'
            tempJson = formateUrl(tempJson)
            if os.path.exists(tempJson) is False:
                open(tempJson, 'w')

            reExt = extractCode(self._repoSrc_)
            if reExt is False:
                logging.error("file extracCode error")

            logging.info("=============Start scan repo==============")
            # 调用scancode
            command = shlex.split(
                'scancode -l -c %s --max-depth 3 --json %s -n 2 --timeout 10 --max-in-memory -1 --license-score 80 --only-findings' % (self._repoSrc_, tempJson))
            resultCode = subprocess.Popen(command)
            while subprocess.Popen.poll(resultCode) == None:
                time.sleep(1)
            popKill(resultCode)

            if self._file_ == 'sourth':
                # 切回master
                self._git_.checkout('master')
                # 删除临时分支
                self._git_.branch('-D', self._branch_)

            scaJson = ''
            # 获取json
            with open(tempJson, 'r+') as f:
                list = f.readlines()
                scaJson = "".join(list)
            logging.info("=============End scan repo==============")

        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.exception("Error on %s: %s" % (command, e))
        finally:
            # 清空文件
            os.chmod(tempJson, stat.S_IWUSR)
            os.remove(tempJson)

            return scaJson

    @catch_error
    def getScaAnalyze(self, scaJson):
        '''
        :param repoSrc: 扫描文件路径
        :param repo: 项目名
        :param scaJson: 扫描结果json
        :return:分析结果json
        '''
        sca_result = {}
        specLicenseList = []
        itemPathList = []

        haveLicense = False
        isCopyright = False
        approved = True
        specLicense = True
        itemLicense = False
        noticeItemLic = '缺少项目级License声明文件'
        itemDetial = {}
        itemLicList = []
        noticeLicense = '缺少项目级License声明文件'
        noticeScope = ''
        noticeSpec = '无spec文件'
        noticeCopyright = '缺少项目级Copyright声明文件'
        speLicDetial = {}

        jsonData = json.loads(scaJson)
        itemPath = jsonpath.jsonpath(jsonData, '$.files[*].path')
        licenseList = jsonpath.jsonpath(jsonData, '$.files[*].licenses')
        copyrightList = jsonpath.jsonpath(jsonData, '$.files[*].copyrights')

        logging.info("=============Start analyze result==============")
        fileLicenseCheck = LicenseCheck('file')
        licenseCheck = LicenseCheck('reference')
        indeLicChck = LicenseCheck('independent')
        for i, var in enumerate(licenseList):
            path = itemPath[i]
            # 判断是否含有notice文件
            if checkNotice(path) and len(copyrightList[i]) > 0:
                if isCopyright is False:
                    isCopyright = True
                    noticeCopyright = ""
                noticeCopyright = noticeCopyright + "(" + path + "), "

            if path.endswith((".spec",)) and self.checkPath(path):
                # 提取spec里的许可证声明
                fileUrl = self._anlyzeSrc_ + "/" + itemPath[i]
                try:
                    spec = Spec.from_file(fileUrl)
                    if spec.license is not None:
                        licenses = infixToPostfix(spec.license)
                        isSpecLicense = licenseCheck.check_license_safe(licenses)
                        specLicense = isSpecLicense.get('pass')
                        noticeSpec = isSpecLicense.get('notice')
                        speLicDetial = isSpecLicense.get('detail')
                        specLicenseList.append(spec.license)
                except Exception as e:
                    logging.exception(e)
                    pass

            if len(var) == 0:
                continue

            for pathLicense in var:
                isLicenseText = pathLicense['matched_rule']['is_license_text']
                spdx_name = pathLicense['spdx_license_key']
                if 'LicenseRef-scancode-' in spdx_name:
                    continue
                spdxLicenses = infixToPostfix(spdx_name)               
                # 判断是否有项目license
                if checkRepoLicense(path) and isLicenseText is True :
                    if haveLicense is False:
                        haveLicense = True
                        noticeLicense = ""
                        #判断项目License是否准入                      
                        if self._owner_ == 'src-openeuler':
                            itemLicCheck = licenseCheck.check_license_safe(spdxLicenses)
                        else:
                            itemLicCheck = indeLicChck.check_license_safe(spdxLicenses)
                        itemLicense = itemLicCheck.get('pass')
                        noticeItemLic = itemLicCheck.get('notice')
                        itemDetial = itemLicCheck.get('detail')
                        itemLicList.append(spdx_name)
                        itemPathList.append(path)
                    elif path.lower().endswith(("license",)) and path not in itemPathList:
                        #判断项目License是否准入                      
                        if self._owner_ == 'src-openeuler':
                            itemLicCheck = licenseCheck.check_license_safe(spdxLicenses)
                        else:
                            itemLicCheck = indeLicChck.check_license_safe(spdxLicenses)
                        itemLicense = itemLicCheck.get('pass')
                        noticeItemLic = itemLicCheck.get('notice')
                        itemDetial = itemLicCheck.get('detail')
                        itemLicList.clear()
                        itemPathList.clear()
                        itemLicList.append(spdx_name)
                        itemPathList.append(path)
                    elif path in itemPathList and spdx_name not in itemLicList: 
                        #同一个文件的做检查
                        if self._owner_ == 'src-openeuler':
                            itemLicCheck = licenseCheck.check_license_safe(spdxLicenses)
                        else:
                            itemLicCheck = indeLicChck.check_license_safe(spdxLicenses)
                        itemLicTemp = itemLicCheck.get('pass')
                        if itemLicTemp is False:
                            itemLicense = itemLicTemp
                            if noticeItemLic != '通过':
                                noticeItemLic = noticeItemLic + "。" + itemLicCheck.get('notice')
                            else:
                                noticeItemLic = itemLicCheck.get('notice')
                            itemDetial = self.mergDetial(itemDetial, itemLicCheck.get('detail')) 
                        itemLicList.append(spdx_name)                       
                else:
                    # 判断license是否属于认证
                    fileLicense = fileLicenseCheck.check_license_safe(spdxLicenses)
                    reLicense = fileLicense.get('pass')
                    if reLicense is False and pathLicense['start_line'] != pathLicense['end_line']:
                        approved = False
                        noticeScope = noticeScope + spdx_name + "("+path + ", start_line: "+str(
                            pathLicense['start_line'])+", end_line: "+str(pathLicense['end_line'])+"), "
        
        if len(itemPathList) == 0:
            itemPathList.append(noticeLicense)
        noticeCopyright = noticeCopyright.strip(', ')
        noticeScope = noticeScope.strip(', ')
        if noticeScope == '':
            noticeScope = 'OSI/FSF认证License'
        else:
            noticeScope = '存在非OSI/FSF认证的License：' + noticeScope

        sca_result = {
            "repo_license_legal": {
                "pass": haveLicense,
                "result_code": "",
                "notice": itemPathList[0],
                "is_legal": {
                    "pass": itemLicense,
                    "license": itemLicList,
                    "notice": noticeItemLic,
                    "detail": itemDetial
                }
            },
            "spec_license_legal": {
                "pass": specLicense,
                "result_code": "",
                "notice": noticeSpec,
                "detail": speLicDetial
            },
            "license_in_scope": {
                "pass": approved,
                "result_code": "",
                "notice": noticeScope
            },
            "repo_copyright_legal": {
                "pass": isCopyright,
                "result_code": "",
                "notice": noticeCopyright
            }
        }
        logging.info("=============End analyze result==============")

        return sca_result

    @catch_error
    def checkPath(self, path):
        # 检查是notice文件
        path = path.lower()

        pathLevel = path.split("/")
        if len(pathLevel) > 3:
            return False

        return True

    @catch_error
    def rmExtract(self, path):
        pathList = path.split("/")

        for item in pathList:
            if '-extract' in item:
                pathList.remove(item)
                break

        return "/".join(pathList)

    @catch_error
    def mergDetial(self,oldDetial,lastDetial):
        res = {}
        impResult = True
        impLic = []
        nstdResult = True
        nstdLic = []
        reviewResult = True
        reviewLic = []
        if oldDetial.get('is_standard').get('pass') is False or lastDetial.get('is_standard').get('pass') is False:
            nstdResult = False
            nstdLic = oldDetial.get('is_standard').get('risks') + lastDetial.get('is_standard').get('risks')

        if oldDetial.get('is_white').get('pass') is False or lastDetial.get('is_white').get('pass') is False:
            impResult = False

        impLic = oldDetial.get('is_white').get('risks') + lastDetial.get('is_white').get('risks')

        blackReason = oldDetial.get('is_white').get('blackReason') + ", " + lastDetial.get('is_white').get('blackReason')
        blackReason = blackReason.strip(", ")
                
        if oldDetial.get('is_review').get('pass') is False or lastDetial.get('is_review').get('pass') is False:
            reviewResult = False
            reviewLic = oldDetial.get('is_review').get('risks') + lastDetial.get('is_review').get('risks')

        res = {
            'is_standard' : {
                'pass': nstdResult,
                'risks' : nstdLic,
            },
            'is_white' : {
                'pass': impResult,
                'risks' : impLic,
                'blackReason' : blackReason,
            },
            'is_review' : {
                'pass': reviewResult,
                'risks' : reviewLic,
            }
        }

        return res
