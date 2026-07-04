---
name: crescendo-init
description: "Initializes a new multi-agent crescendo project by cloning the crescendo-agent-template-claude and guiding the user on dropping in project files."
_upstream_source: conductor
_upstream_version: 1.0.0
---

# Crescendo Project Initialization Skill

This skill is designed to help novice and experienced users easily spin up a new orchestration-ready repository based on the `{ORG_NAME}/crescendo-agent-template-claude`.

> **Note:** The default template repository is `crescendo-agent-template-claude`. If you need a different template, the user can specify it.

When the user asks to initialize a crescendo project or create a new crescendo setup, follow these steps **exactly and in order**:

---

## 0. Resolve GitHub Organization

Before proceeding, you MUST determine the user's GitHub organization name:
1. Check if the user has already provided a GitHub org name in their prompt.
2. If not, check for an `ORG_NAME` variable in the project's environment or configuration files.
3. If still not found, **ask the user**: "What is your GitHub organization name? (e.g., `my-org`)"
4. Store this as `{ORG_NAME}` and use it throughout the remaining steps.

---

## 1. Gather Project Name

Ask the user what they want to name their new project/repository (if they haven't provided it already in their prompt). The name should be lower-case with hyphens (e.g., `my-new-project`).

---

## 2. Scaffold the Repository

Once you have the `<project-name>` and `{ORG_NAME}`, execute the following GitHub CLI command to create the new private repository from the template and clone it locally into the active workspace directory:

```bash
gh repo create {ORG_NAME}/<project-name> --template {ORG_NAME}/crescendo-agent-template-claude --private --clone
```

---

## 3. Domain Profile Selection

> [!IMPORTANT]
> This step is **mandatory**. You must NEVER skip it or dynamically generate a profile from user input. Only pre-built profiles shipped with the template are allowed.

After the repository has been cloned successfully, you **MUST** do the following:

### 3a. Discover Available Profiles

List the contents of the `conductor/profiles/` directory inside the newly cloned repository. Each `.json` file in that directory is a pre-built domain profile.

### 3b. Read & Summarize Each Profile

For every profile file found, read its contents and extract a brief summary including:

| Field                    | What to show the user                                         |
| ------------------------ | ------------------------------------------------------------- |
| **Domain Name**          | The domain or industry the profile is designed for            |
| **Isolation Strategy**   | e.g., `worktree`, `branch`, `monorepo`                       |
| **Data Classification**  | e.g., `public`, `internal`, `confidential`, `restricted`     |
| **Max Agents**           | The maximum number of parallel subagents allowed              |
| **Key Quality Gates**    | Any review, test, or approval gates defined in the profile    |

### 3c. Ask the User to Choose

Present the list of profiles to the user using the **AskUserQuestion** tool. Each option should show the domain name and a one-line summary. Example option text:

```
Real Estate — confidential data, worktree isolation, 4 max agents
```

**Rules:**
- Do **NOT** dynamically generate or invent a profile based on user input.
- If no profiles are found in `conductor/profiles/`, stop and inform the user that the template appears to be missing profiles, and ask them to verify the template version.

### 3d. Copy the Selected Profile

Once the user selects a profile, copy it to the project root as the active profile:

```bash
cp conductor/profiles/<selected-profile>.json conductor/profile.json
```

### 3e. Custom Profiles

If the user expresses a desire for a profile that doesn't exist in the list:
- **Do NOT** attempt to generate one.
- Instead, instruct the user:
  > "Custom profiles are not auto-generated. Please select the closest pre-built profile for now. After setup is complete, you can manually edit `conductor/profile.json` to tailor it to your needs."

---

## 4. Profile Confirmation

> [!CAUTION]
> You **MUST** wait for explicit user confirmation before proceeding past this step. Do not continue silently.

After copying the selected profile to `conductor/profile.json`:

### 4a. Display the Full Profile

Print the **entire contents** of `conductor/profile.json` to the user so they can review every field.

### 4b. Ask for Explicit Confirmation

After displaying the profile, ask the user clearly:

> **"I have selected the `[domain]` profile with `[data_classification]` classification and `[max_agents]` max agents. Confirm this is correct before I proceed?"**

Replace `[domain]`, `[data_classification]`, and `[max_agents]` with the actual values from the selected profile.

### 4c. Handle the Response

- **If confirmed** → proceed to Step 5.
- **If rejected** → return to Step 3c and let the user pick a different profile.
- **If the user wants edits** → remind them they can manually edit `conductor/profile.json` after setup, then ask if they'd like to proceed with the current selection or pick a different one.

---

## 5. Navigate & Verify

Navigate into the newly cloned directory (if not already there):

```bash
cd <project-name>
```

Verify that the scaffolding was successfully cloned by checking for the existence of:
- `conductor/bin/`
- `justfile`
- `input/` directory
- `conductor/profile.json` (the profile you just copied)

---

## 6. Provide Novice-Friendly Instructions

Stop executing tools and print a clear, welcoming message to the user explaining the next steps:

> **Crescendo Setup Complete!** 🎉
> 
> I have created your new repository `{ORG_NAME}/<project-name>` from the Crescendo template and cloned it locally.
> 
> **Active Domain Profile:** `[domain]` (`[data_classification]` classification, `[max_agents]` max agents)
> 
> **Next Steps:**
> 1. In your editor, open the new folder: `<project-name>`.
> 2. Open the `input/` folder and drop your project's PRD (Product Requirements Document), UI mockups, architecture diagrams, or any constraints there.
> 3. If you need to customize the domain profile, edit `conductor/profile.json` directly.
> 4. Once you've added your files, come back here and say: *"Read the files in the input folder and initialize the Crescendo workflow."*
> 
> I'll then launch parallel subagents to implement your project across isolated Git Worktrees!
