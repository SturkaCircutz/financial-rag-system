pipeline {
    agent any

    options {
        skipDefaultCheckout(true)
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '20'))
        timeout(time: 45, unit: 'MINUTES')
    }

    parameters {
        booleanParam(name: 'BUILD_DOCKER_IMAGE', defaultValue: false, description: 'Build local backend and RAG Docker images on Jenkins agents with Docker.')
    }

    environment {
        CI = 'true'
        MAVEN_OPTS = '-Dspring.output.ansi.enabled=always'
        PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Verify Tools') {
            steps {
                sh 'java -version'
                sh 'mvn -version'
                sh 'python3 --version'
                sh 'node --version'
                sh 'npm --version'
                sh '''
                    if [ "${BUILD_DOCKER_IMAGE}" = "true" ]; then
                      docker --version
                    fi
                '''
            }
        }

        stage('Secret Hygiene') {
            steps {
                sh '''
                    if git grep -nE 'sk-[A-Za-z0-9_-]{20,}' -- .; then
                      echo 'Potential OpenAI-style secret found in tracked files.'
                      exit 1
                    fi
                '''
            }
        }

        stage('Checks') {
            parallel {
                stage('Backend') {
                    stages {
                        stage('Test Backend') {
                            steps {
                                sh './scripts/check.sh'
                            }
                        }

                        stage('Package Backend') {
                            steps {
                                dir('backend') {
                                    sh 'mvn -DskipTests package'
                                }
                            }
                        }
                    }
                    post {
                        always {
                            junit allowEmptyResults: true, testResults: 'backend/target/surefire-reports/*.xml'
                        }
                        success {
                            archiveArtifacts artifacts: 'backend/target/*.jar', fingerprint: true
                        }
                    }
                }

                stage('RAG Service') {
                    stages {
                        stage('Install RAG Dependencies') {
                            steps {
                                sh '''
                                    venv_python="$(pwd)/.jenkins-venv/bin/python"
                                    python3 -m venv .jenkins-venv
                                    "$venv_python" -m pip install --upgrade pip
                                    "$venv_python" -m pip install -e "rag-service[dev]"
                                '''
                            }
                        }

                        stage('Test RAG Service') {
                            steps {
                                sh '''
                                    repo_root="$(pwd)"
                                    mkdir -p rag-service/target
                                    cd rag-service
                                    "$repo_root/.jenkins-venv/bin/python" -m pytest --junitxml=target/pytest-results.xml
                                '''
                            }
                        }
                    }
                    post {
                        always {
                            junit allowEmptyResults: true, testResults: 'rag-service/target/pytest-results.xml'
                        }
                    }
                }

                stage('Frontend') {
                    stages {
                        stage('Install Frontend Dependencies') {
                            steps {
                                dir('frontend') {
                                    sh 'npm ci'
                                }
                            }
                        }

                        stage('Test Frontend') {
                            steps {
                                dir('frontend') {
                                    sh '''
                                        mkdir -p target
                                        npm test -- --reporter=default --reporter=junit --outputFile=target/vitest-results.xml
                                    '''
                                }
                            }
                        }

                        stage('Build Frontend') {
                            steps {
                                dir('frontend') {
                                    sh 'npm run build'
                                }
                            }
                        }
                    }
                    post {
                        always {
                            junit allowEmptyResults: true, testResults: 'frontend/target/vitest-results.xml'
                        }
                        success {
                            archiveArtifacts artifacts: 'frontend/dist/**', allowEmptyArchive: true, fingerprint: true
                        }
                    }
                }
            }
        }

        stage('Validate Compose') {
            steps {
                sh '''
                    if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
                      OPENAI_API_KEY= docker compose config --quiet
                    else
                      echo 'Docker Compose is not installed; skipping compose validation.'
                    fi
                '''
            }
        }

        stage('Build Docker Images') {
            when {
                expression { return params.BUILD_DOCKER_IMAGE }
            }
            steps {
                sh './scripts/docker-build-backend.sh financial-rag-backend:${BUILD_NUMBER}'
                sh 'docker build -t financial-rag-service:${BUILD_NUMBER} rag-service'
            }
        }
    }
}
