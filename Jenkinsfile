pipeline {
    agent any

    stages {
        stage('Checkout') {
            steps {
                echo 'Jenkins is checking out the source code.'
                checkout scm
            }
        }

        stage('Build') {
            steps {
                echo 'Build stage started.'
                bat 'git --version'
            }
        }

        stage('Test') {
            steps {
                echo 'Test stage started.'
            }
        }
    }

    post {
        success {
            echo 'Pipeline completed successfully!'
        }
        failure {
            echo 'Pipeline failed. Check the console output.'
        }
    }
}