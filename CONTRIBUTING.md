# Contributing to AWS S3 Vectors RAG Application

We welcome contributions to the AWS S3 Vectors RAG Application! This document provides guidelines for contributing to the project.

## 🤝 How to Contribute

### Reporting Issues

1. Check if the issue already exists in the [Issues](https://github.com/ColeMurray/aws-rag-s3-vectors/issues) section
2. If not, create a new issue with:
   - Clear title and description
   - Steps to reproduce (if applicable)
   - Expected vs actual behavior
   - Environment details (Python version, AWS region, etc.)

### Submitting Pull Requests

1. **Fork the repository** and create your branch from `main`
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   pip install pytest pytest-asyncio black isort
   ```
3. **Make your changes**:
   - Follow the existing code style
   - Add tests for new functionality
   - Update documentation as needed
4. **Run tests and linting**:
   ```bash
   # Run tests
   pytest tests/
   
   # Format code
   black src/ scripts/ tests/
   isort src/ scripts/ tests/
   ```
5. **Commit your changes**:
   - Use clear, descriptive commit messages
   - Reference issues when applicable (e.g., "Fix #123: Add error handling")
6. **Push to your fork** and submit a pull request

### Code Style

- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/)
- Use type hints where appropriate
- Add docstrings to functions and classes
- Keep functions focused and small
- Use meaningful variable names

### Testing

- Write tests for new features
- Ensure all tests pass before submitting PR
- Aim for good test coverage
- Use mocks for AWS services in tests

## 📋 Development Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/ColeMurray/aws-rag-s3-vectors.git
   cd aws-rag-s3-vectors
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install development dependencies**:
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt  # If available
   ```

4. **Set up pre-commit hooks** (optional):
   ```bash
   pip install pre-commit
   pre-commit install
   ```

## 🏗️ Architecture Guidelines

When contributing, please consider:

- **Modularity**: Keep components loosely coupled
- **Error Handling**: Always handle AWS service errors gracefully
- **Performance**: Consider rate limits and optimize batch operations
- **Security**: Never commit credentials or sensitive data
- **Documentation**: Update docs for new features or API changes

## 📚 Documentation

- Update README.md for user-facing changes
- Add inline comments for complex logic
- Update API documentation (docstrings)
- Include examples for new features

## 🔍 Review Process

1. All submissions require review before merging
2. Reviewers will check for:
   - Code quality and style
   - Test coverage
   - Documentation updates
   - Breaking changes
   - Security considerations

## 📜 License

By contributing, you agree that your contributions will be licensed under the MIT License.

## 🙏 Thank You!

Thank you for contributing to the AWS S3 Vectors RAG Application! Your efforts help make this project better for everyone.