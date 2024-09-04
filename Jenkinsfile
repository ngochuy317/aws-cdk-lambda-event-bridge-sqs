#!/usr/bin/env groovy

def getEnvironments() {
    return [
      "branch_to_deploy": [
        "develop",
        "feature-deploy/.*",
        "release/.*",
        "main"
      ],
      "infra_branch_to_deploy": [
        "develop",
        "main"
      ],
      "target": [
        "dev": [
          "account": "642432130542"
        ],
        "stg": [
          "account": "136763156751"
        ],
        "prod": [
          "account": "704639331327"
        ]
      ]
    ]
}

def isBranchDeployable(environments, branch) {
    def deploy_branch = environments["branch_to_deploy"].findAll{branch ==~ /$it/}

    print "Branch : ${deploy_branch}"

    return deploy_branch.size() > 0
}

def isBranchInfraDeployable(environments, branch) {
    def deploy_branch = environments["infra_branch_to_deploy"].findAll{branch ==~ /$it/}

    print deploy_branch

    return deploy_branch.size() > 0
}

def is_full_build = env.CHANGE_BRANCH ? false : true
def branch = env.CHANGE_BRANCH ? env.CHANGE_BRANCH : env.GIT_BRANCH
def env_to_deploy = 'dev'
def build_warnings = []
def sec_audit = 'Not executed'
def is_pytest_successful = 'Not executed'
def coverage_perc = 'Not executed'
def pylint_perc = 'Not executed'
def changed_etls = []


pipeline {
    agent any
    environment {
        IMAGE_TAG = GIT_COMMIT.take(7)
        JFROG_CREDENTIALS = credentials('jfrog')
        JFROG_NPMRC_FILE = credentials('jfrog_npmrc')
    }

    stages {
        stage("Set env") {
            steps {
                //cleanWs() // Completely purges workspace, one time action, uncomment when absolutely needed
                script {
                    def environments = getEnvironments()
                    branch = env.CHANGE_BRANCH ? env.CHANGE_BRANCH : env.GIT_BRANCH

                    if (is_full_build && branch == 'main') {
                        env_to_deploy = 'prod'
                    }
                    if (is_full_build && (branch == 'develop' || branch.startsWith('release'))) {
                        env_to_deploy = 'stg'
                    }

                    env.ACCOUNT = environments["target"][env_to_deploy].account.trim()

                    if (isBranchDeployable(environments, branch)) {
                        env.DEPLOY = true
                    }

                    if (isBranchInfraDeployable(environments, branch)) {
                        env.INFRA_DEPLOY = true
                    }
                    print "Branch: ${branch}, env: ${env_to_deploy}, deploy: ${env.DEPLOY}"
                }
            }
        }

        stage("Code CI/CD") {
            agent {
               docker {
                   image "python:3.10.12-alpine3.18"
                   args "-v /etc/passwd:/etc/passwd -u root:root"
                   reuseNode true
              }
            }
            stages {
                stage("Code Build") {
                    stages {
                        stage("Get changed modules") {
                            steps {
                                script {
                                    if (!is_full_build) {
                                        def changedFiles = pullRequest.files.collect {
                                            it.getFilename()
                                        }

                                        changedFiles.each() { value ->
                                            if (value.contains('apps') &&
                                              ! (value in ['apps/README.md', 'apps/requirements.txt', 'apps/__init__.py', 'apps/pylintrc'])) {
                                                module_root = value.replace('apps/', '').split('/')[0]
                                                changed_etls << module_root
                                            }
                                        }

                                        changed_etls.unique()
                                    } else {
                                        def subdirs = sh(
                                            returnStdout: true,
                                            script: "ls -d apps/*"
                                        ).trim()

                                        subdirs.split('\n').each() { value ->
                                            if (!value.contains('.') & !(value in ['apps/README.md', 'apps/requirements.txt', 'apps/__init__.py', 'apps/pylintrc', '__pycache__'])) {
                                                module_root = value.replace('apps/', '').split('/')[0]
                                                changed_etls << module_root
                                            }
                                        }
                                    }

                                    print changed_etls
                                }
                            }
                        }

                        stage("Test & Analyze") {
                            parallel {
                                stage("Security check") {
                                    steps {
                                        script {
                                            if (fileExists('local-install')) {
                                                sh 'rm -r local-install'
                                            }

                                            sh "python3 -m pip install pip-audit -t local-install"

                                            dir("local-install"){
                                                def l_audit = sh (
                                                    script: "python3 -m pip_audit -r ../requirements-dev.txt -l --desc on -o sec_audit_${BUILD_ID}.txt 2>&1 | tee sec_audit_${BUILD_ID}.txt",
                                                    returnStatus: true
                                                )

                                                sec_audit = l_audit != 0
                                            }

                                            if (!fileExists('audit_reports')) {
                                                sh 'mkdir audit_reports'
                                            }

                                            sh "cp local-install/sec_audit_${BUILD_ID}.txt audit_reports"
                                            sh "rm -r local-install"

                                            if (sec_audit) {
                                                throw new Exception("Vulnerabilities have been detected, please check sec_audit_${BUILD_ID}.txt file for more details.")
                                            }
                                        }
                                    }
                                }

                                stage("Execute unit tests") {
                                    steps {
                                        sh "python3 -m pip install -r requirements-dev.txt"
                                        script {
                                            test_folders = ""

                                            if (fileExists('pytest_reports')) {
                                                sh 'rm -r pytest_reports'
                                            }

                                            if (fileExists("xml_reports")) {
                                                sh "rm -r xml_reports"
                                            }

                                            if (fileExists('pytest_reports/htmlcov')) {
                                                sh 'rm -r pytest_reports/htmlcov'
                                            }

                                            sh 'mkdir pytest_reports'
                                            sh "mkdir xml_reports"

                                            test_folders = changed_etls.findAll{ fileExists("apps/${it}") }.join(" ")

                                            if (test_folders != "") {
                                                dir("apps"){
                                                    def pytest_run = sh (
                                                        script: "python3 -m coverage run --omit='/usr/*' -m pytest ${test_folders} --junitxml=xml_report_${BUILD_ID}.xml --html=pytest_report_${BUILD_ID}.html --self-contained-html",
                                                        returnStatus: true
                                                    )

                                                    is_pytest_successful = pytest_run == 0

                                                    if (!is_pytest_successful) {
                                                        throw new Exception("Unit test execution has failed, please check pytest_report_${BUILD_ID}.html file for more details.")
                                                    }

                                                    def coverage_report = sh (
                                                        script: "python3 -m coverage report --omit='/usr/*'",
                                                        returnStdout: true
                                                    ).trim()

                                                    print coverage_report
                                                    coverage_perc = coverage_report.split('\n').last().split(' ').last()

                                                    sh (
                                                        script: "python3 -m coverage html --omit='/usr/*'",
                                                        returnStatus: true
                                                    )
                                                }
                                            } else {
                                                is_pytest_successful = true
                                            }

                                            if (test_folders != "") {
                                                sh "cp apps/pytest_report_${BUILD_ID}.html pytest_reports"
                                                sh "cp apps/xml_report_${BUILD_ID}.xml xml_reports"

                                                if (fileExists("htmlcov")) {
                                                    sh "cp -r apps/htmlcov pytest_reports/htmlcov"

                                                    if (coverage_perc.replace('%', '').toInteger()<80) {
                                                        throw new Exception("The unit test coverage ${coverage_perc} is lower then 80%, please check Unit test coverage report for more details.")
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }


                stage("Code deploy") {
                    when { expression {env.DEPLOY} }
                    stages {
                        stage("Zip changed modules") {
                            steps {
                                sh "apk add zip"
                                script {
                                    dir("apps") {
                                        if (fileExists('target')) {
                                            sh 'rm -r target'
                                        }

                                        sh 'mkdir target'
                                        sh 'mkdir target/sms'

                                        changed_etls.findAll{it != 'common'}.each() {etl ->
                                            if (fileExists("${etl}/requirements.txt")) {
                                                sh "python3 -m pip install -r ${etl}/requirements.txt -t ${etl}"
                                            }
                                            sh "zip -r target/${etl}.zip ${etl} common -x \"**/test/*\" -x \"**/common/test/*\" -x \"common/test/*\" -x \"**/__pycache__/*\""
                                        }
                                    }
                                }
                            }
                        }

                        stage("Deploy changed modules to S3") {
                            steps {
                                script {
                                    withAWS(role:"oma-${env_to_deploy}-omf-cld360-development-jenkins_iam_role-ue1-all",
                                            roleAccount:"${env.ACCOUNT}",
                                            duration: 900,
                                            region: "us-east-1",
                                            roleSessionName: 'jenkins-session') {
                                        def tags = [:]
                                        tags["BUILD_ID"] = "${BUILD_ID}"

                                        s3Upload(bucket:"cld360-s3-${env_to_deploy}-artifacts-ue1-all", path:'artifacts/omf-ma-sms-provisioning-deprovisioning-team-members', includePathPattern:'**/*', workingDir:"apps/target", tags: tags.toString())
                                    }
                                }
                            }
                        }
                    }
                }

            }
        }

        stage("Infrastructure CI/CD") {
		    when { expression {env.INFRA_DEPLOY} }
		    agent {
               docker {
                   image "node:lts-alpine3.18"
                   args "-v /etc/passwd:/etc/passwd -u root:root"
                   reuseNode true
              }
            }
		    stages {
		        stage("Install dependencies"){
		            steps {
                        sh "apk add --no-cache python3 py3-pip"
                        sh "npm install -g aws-cdk"
                        sh "pip install -r requirements.txt"
		            }
		        }

		        stage("Infrastructure build") {
		            stages {
		                stage("Synthesize") {
		                    steps {
                                script {
                                    if (fileExists("${env.GIT_COMMIT}")) {
                                        sh "rm -r ${env.GIT_COMMIT}"
                                    }

                                    withAWS(role:"oma-${env_to_deploy}-omf-cld360-development-jenkins_iam_role-ue1-all",
                                            roleAccount:"${env.ACCOUNT}",
                                            duration: 3600,
                                            region: "us-east-1",
                                            roleSessionName: 'jenkins-session') {
                                        sh "cdk synth -c env=${env_to_deploy} -o ${env.GIT_COMMIT}"
                                    }
                                }
                            }
		                }
		            }
		        }

		        stage("Infrastructure deploy") {
		            stages {
		                stage("Deploy changed resources") {
		                    steps {
                                script {
                                    withAWS(role:"oma-${env_to_deploy}-omf-cld360-development-jenkins_iam_role-ue1-all",
                                            roleAccount:"${env.ACCOUNT}",
                                            duration: 3600,
                                            region: "us-east-1",
                                            roleSessionName: 'jenkins-session') {
                                        def cdk_deploy = sh (
                                            script: "cdk deploy '**' --app ${env.GIT_COMMIT} --ci --require-approval never -c env=${env_to_deploy}",
                                            returnStdout: true
                                        )

                                        print cdk_deploy
                                    }
                                }
                            }
		                }
		            }
		        }
		    }
		}

    }

    post {
        // Clean after build
        always {
            cleanWs(cleanWhenNotBuilt: false,
                    deleteDirs: true,
                    disableDeferredWipeout: true,
                    notFailBuild: true,
                    patterns: [[pattern: '.gitignore', type: 'INCLUDE'],
                               [pattern: '.propsfile', type: 'EXCLUDE']])
        }
    }
}