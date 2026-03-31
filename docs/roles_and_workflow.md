# Roles and Workflow

## Overview

This project simulates a real-world development lifecycle by separating responsibilities into two roles:

- Developer
- Tester

This approach reflects best practices in data and AI projects.

---

## Developer Role

### Responsibilities

- Design and implement data pipelines in Microsoft Fabric
- Develop preprocessing notebooks
- Build and structure datasets
- Train AI models using Azure AI Foundry
- Maintain and update the GitHub repository

### Environment

- Workspace: `pet-recognition-dev`
- Permissions: Admin / Member

### Key Activities

- Create and configure pipelines
- Implement image preprocessing logic
- Generate multi-resolution datasets
- Document architecture and decisions

---

## Tester Role

### Responsibilities

- Execute pipelines in test environment
- Validate processed datasets
- Perform quality checks on images
- Review model outputs and performance
- Report issues and inconsistencies

### Environment

- Workspace: `pet-recognition-test`
- Permissions: Viewer / Contributor

### Key Activities

- Run pipeline executions
- Verify dataset structure and completeness
- Validate image transformations
- Ensure reproducibility of results

---

## Workflow

The interaction between roles follows this sequence:

1. Developer builds and updates pipeline
2. Code and notebooks are exported to GitHub
3. Tester executes pipeline in test workspace
4. Tester validates outputs and reports feedback
5. Developer applies improvements

---

## Benefits of Role Separation

- Improves reliability and quality control
- Mimics enterprise-level workflows
- Enhances collaboration and accountability
- Provides clearer project structure for stakeholders

---

## Integration with GitHub

- Developer pushes updates to repository
- Tester reviews outputs based on documented behavior
- Changes are tracked and versioned

---

## Summary

This role-based approach ensures that the solution is:

- Scalable
- Maintainable
- Testable
- Aligned with industry best practices
