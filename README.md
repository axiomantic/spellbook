<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Spellbook](#spellbook)
  - [Prerequisites](#prerequisites)
  - [Quick Install](#quick-install)
  - [What's Included](#whats-included)
    - [Skills (26 total)](#skills-26-total)
    - [Commands (15 total)](#commands-15-total)
    - [Agents (1 total)](#agents-1-total)
  - [Platform Support](#platform-support)
    - [Autonomous Mode](#autonomous-mode)
  - [Playbooks](#playbooks)
    - [Large Feature with Context Exhaustion](#large-feature-with-context-exhaustion)
    - [Test Suite Audit and Remediation](#test-suite-audit-and-remediation)
    - [Parallel Worktree Development](#parallel-worktree-development)
    - [Cross-Assistant Handoff](#cross-assistant-handoff)
  - [Recommended Companion Tools](#recommended-companion-tools)
    - [Heads Up Claude](#heads-up-claude)
    - [MCP Language Server](#mcp-language-server)
  - [Development](#development)
    - [Serve Documentation Locally](#serve-documentation-locally)
    - [Run MCP Server Directly](#run-mcp-server-directly)
  - [Documentation](#documentation)
  - [Contributing](#contributing)
  - [Acknowledgments](#acknowledgments)
  - [Attribution](#attribution)
  - [License](#license)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<p align="center">
  <img src="./docs/assets/logo.svg" alt="Spellbook" width="120" height="120">
</p>

<h1 align="center">Spellbook</h1>

<p align="center">
  <em>Principled development on autopilot. Decades of engineering expertise, built in.</em><br>
  For Claude Code, OpenCode, Codex, Gemini CLI, and Crush.
</p>

<p align="center">
  <a href="https://github.com/axiomantic/spellbook/blob/main/LICENSE"><img src="https://img.shields.io/github/license/axiomantic/spellbook?style=flat-square" alt="License"></a>
  <a href="https://github.com/axiomantic/spellbook/stargazers"><img src="https://img.shields.io/github/stars/axiomantic/spellbook?style=flat-square" alt="Stars"></a>
  <a href="https://github.com/axiomantic/spellbook/issues"><img src="https://img.shields.io/github/issues/axiomantic/spellbook?style=flat-square" alt="Issues"></a>
  <a href="https://axiomantic.github.io/spellbook/"><img src="https://img.shields.io/badge/docs-GitHub%20Pages-blue?style=flat-square" alt="Documentation"></a>
</p>

<p align="center">
  <a href="https://github.com/axiomantic/spellbook"><img src="https://img.shields.io/badge/Built%20with-Spellbook-6B21A8?style=for-the-badge&logo=data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiPz4KPHN2ZyB3aWR0aD0iMTIwMHB0IiBoZWlnaHQ9IjEyMDBwdCIgdmVyc2lvbj0iMS4xIiB2aWV3Qm94PSIwIDAgMTIwMCAxMjAwIiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciPgogPHBhdGggZmlsbD0iI0ZGRiIgZD0ibTI4LjQ0MSA1MDkuMjhjMC42MDE1NiA1LjAzOTEgMi4yODEyIDkuMzU5NCAzLjcxODggMTMuODAxIDMuMTIxMSA4LjY0MDYgNy4zMjAzIDE2LjA3OCAxMS43NjIgMjIuNjggOC44Nzg5IDEzLjA3OCAxOC42MDIgMjMuODc5IDI4LjU1OSAzMy40OCAxOS44MDEgMTkuNDQxIDQwLjMyIDM1LjY0MSA2MC44NCA1MS43MTkgNDEuMTYgMzEuNjggODIuNTU5IDYxLjU1OSAxMjMuNzIgOTEuOTIybDIzLjY0MSAxNy4yODFjLTUuMTYwMiAxNS42MDItMTAuNDQxIDMxLjMyLTE1LjYwMiA0Ny4wMzktMTYuMDc4IDQ4LjQ4LTMyLjY0MSA5Ni43MTktNDcuNjQxIDE0Ni44OC03LjMyMDMgMjUuMTk5LTE0LjUyIDUwLjc2Mi0xOS4wNzggNzkuMzItMS45MjE5IDE0LjUyLTMuNjAxNiAyOS43NjItMS41NTg2IDQ4IDEuMTk5MiA5LjEyMTEgMy4yMzgzIDE5LjA3OCA3LjkyMTkgMjkuMTZsMy43MTg4IDcuNTU4NmMxLjMyMDMgMi42NDA2IDIuMzk4NCAzLjk2MDkgMy42MDE2IDYgMi4zOTg0IDMuNzE4OCA1LjAzOTEgNy4zMjAzIDcuOTIxOSAxMC44MDEgMTEuMjgxIDEzLjkyMiAyNS40NDEgMjUuNTU5IDQxLjM5OCAzMy44NCA4LjAzOTEgNC4xOTkyIDE2LjQ0MSA3LjU1ODYgMjUuMDc4IDkuOTYwOSAxLjkyMTkgMC42MDE1NiA0LjY3OTcgMS4xOTkyIDcuNTU4NiAxLjY3OTdsOC41MTk1IDEuMzIwM2M1LjUxOTUgMC40ODA0NyAxMC42OCAwLjIzODI4IDE2LjA3OCAwLjIzODI4IDIwLjM5OC0xLjY3OTcgMzUuNTItNy44MDA4IDQ5LjQ0MS0xMy42OCAxNC4wMzktNiAyNi4xNi0xMi44NCAzOC4xNi0xOS42OCA0Ni45MjItMjcuODQgODguMDc4LTU3Ljk2MSAxMzAuMDgtODcuMzU5IDI0Ljk2MS0xNy42NDEgNTEuNjAyLTM2LjYwMiA3OC43MTktNTYuMDM5bDEzLjA3OCA5LjYwMTZjNDEuMjgxIDMwLjEyMSA4Mi4xOTkgNjAuNjAyIDEyNC44IDkwLjIzOCAyMS40OCAxNC43NjIgNDMuMDc4IDI5LjM5OCA2Ny4zMiA0Mi40OCAxMi4xMjEgNi40ODA1IDI1LjA3OCAxMi42MDIgMzkuOTYxIDE3LjI4MSAzLjk2MDkgMC45NjA5NCA3LjU1ODYgMi4xNjAyIDExLjc2MiAzIDQuMzIwMyAwLjYwMTU2IDguMzk4NCAxLjQ0MTQgMTIuODQgMS42Nzk3IDQuNjc5NyAwIDkuMTIxMSAwLjQ4MDQ3IDE0LjAzOS0wLjM1OTM4IDQuODAwOC0wLjcxODc1IDEwLjA3OC0xLjU1ODYgMTMuNjgtMi42NDA2IDE1LjcxOS00LjQ0MTQgMzAuNDgtMTIuMjM4IDQzLjA3OC0yMi42OCA2LjIzODMtNS4xNjAyIDEyLTExLjAzOSAxNy4xNi0xNy4zOThzOS4zNTk0LTEyLjcxOSAxMy42OC0yMi4xOTljNy41NTg2LTE3Ljg3OSA3LjY3OTctMzQuNDQxIDcuMDc4MS00OS4wNzgtMC44Mzk4NC0xNC43NjItMy0yOC41NTktNS42NDA2LTQxLjc2Mi0xMS4xNi01Mi42OC0yNy40OC0xMDEuMTYtNDIuNzE5LTE1MC4xMmwtMzUuMzk4LTExMC4yOGMyMS4xMjEtNi4yMzgzIDQ5LjgwMS0yMy4xNiA4MS44NC00NC43NjIgMjguNTU5LTE5LjE5OSA1OS42NDEtNDIuMzU5IDkwLTY3LjE5OSAxNS4xMjEtMTIuNDggMzAtMjUuNDQxIDQ0LjE2LTM5LjIzOCAxMy45MjItMTMuOTIyIDI3LjQ4LTI4LjY4IDM3LjU1OS00OC4xMjEgMS45MjE5LTMuODM5OCAzLjgzOTgtNy42Nzk3IDUuMTYwMi0xMi4yMzhsMi4xNjAyLTYuNjAxNiAxLjMyMDMtNy4xOTkyYzAuOTYwOTQtNS4xNjAyIDEuMDc4MS05LjEyMTEgMS4xOTkyLTEzLjE5OSAwLTQuMDc4MSAwLTguMTYwMi0wLjQ4MDQ3LTEyLjIzOC0xLjQ0MTQtMTYuMzItNi4xMjExLTMyLjM5OC0xMy44MDEtNDYuODAxLTMuODM5OC03LjE5OTItOC4zOTg0LTE0LjE2LTEzLjY4LTIwLjM5OC0zLjIzODMtMy40ODA1LTYuODM5OC03LjMyMDMtMTAuNDQxLTEwLjMyLTMuNzE4OC0yLjY0MDYtNy41NTg2LTUuODc4OS0xMS4zOTgtNy44MDA4LTE1LjQ4LTguODc4OS0zMC4yMzgtMTIuODQtNDQuMjgxLTE1LjcxOS0yOC4xOTktNS43NjE3LTU0LjM1OS02Ljk2MDktODAuNTItOC4yODEyLTI2LjE2LTEuMDc4MS01MS44NC0xLjQ0MTQtNzcuNTItMS41NTg2aC0xMjYuOTZsLTM1LjY0MS0xMTIuMDhjLTcuOTIxOS0yNC4zNTktMTUuODQtNDguODQtMjQuNDgtNzMuNDQxLTguNzYxNy0yNC42MDItMTcuNzYyLTQ5LjE5OS0zMC4xMjEtNzQuMTYtNi4yMzgzLTEyLjQ4LTEzLjE5OS0yNS4wNzgtMjMuNjQxLTM3LjgwMS01LjE2MDItNi4yMzgzLTExLjM5OC0xMi40OC0xOS4zMi0xOC0zLjYwMTYtMi44Nzg5LTguNTE5NS01LjAzOTEtMTIuODQtNy4zMjAzLTQuMTk5Mi0xLjkyMTktNy44MDA4LTMuMTIxMS0xMS44NzktNC40NDE0LTE1Ljg0LTUuMDM5MS0zMi43NjItNi42MDE2LTQ5LjE5OS00LjgwMDgtMTYuNTU5IDIuMjgxMi0zMi4wMzkgNS43NjE3LTQ5LjE5OSAxOC0xNS4xMjEgMTEuNTItMjQuMTIxIDI0LjcxOS0zMS45MjIgMzcuMDc4LTcuNTU4NiAxMi42MDItMTMuNDQxIDI0Ljk2MS0xOS4wNzggMzcuNDQxLTEwLjkyMiAyNC43MTktMTkuNjggNDkuMTk5LTI4LjMyIDczLjY4LTE4LjM1OSA1NS4xOTktMzYuNjAyIDExMC40LTU0Ljk2MSAxNjUuNDhoLTk1Ljg3OWMtNTEuMzU5IDAuNDgwNDctMTAyLjM2LTAuMjM4MjgtMTU2LjI0IDUuMjgxMi0xMy40NDEgMS4zMjAzLTI3LjM1OSAzLjcxODgtNDEuNzYyIDcuMzIwMy0xNC4yODEgMy44Mzk4LTMwLjEyMSA5LjIzODMtNDUuMjM4IDIxLjk2MS0zLjQ4MDUgMy4zNTk0LTcuNTU4NiA3LjMyMDMtMTAuMDc4IDEwLjQ0MS0yLjY0MDYgMy4yMzgzLTUuMDM5MSA2LjYwMTYtNy4zMjAzIDkuOTYwOS00LjU1ODYgNi45NjA5LTguMjgxMiAxNC4yODEtMTEuMjgxIDIxLjk2MS02IDE1LjM1OS05IDMxLjkyMi04LjUxOTUgNDguMzU5bDAuMzU5MzggNi4yMzgzIDEuMDc4MSA3LjMyMDN6bTcxNi42NC02NS42NDEgNjguNjQxIDIxMyAyNS4wNzggNzcuODc5Yy01NCAyMS42MDItMTQ4LjMyIDg3LjQ4LTIzOC42OCAxNTNsLTguMzk4NC02LjEyMTEtMjIyLjEyLTE2My42OCA4Ny44NC0yNzQuMzJoMTI3LjJsMTYwLjU2IDAuMzU5Mzd6bS0yNDUuMDQgNTE2Ljk2Yy00MC4zMiAyOS4yODEtODAuNTIgNTkuMTYtMTIwLjM2IDg1LjA3OC0xOS42OCAxMi43MTktNDAuMTk5IDI0Ljg0LTU2LjM5OCAzMC4zNTktNy45MjE5IDIuODc4OS0xMy42OCAzLTEzLjkyMiAyLjc2MTdoLTAuMjM4MjhjLTAuMjM4MjggMC0wLjcxODc1LTAuMjM4MjgtMS4wNzgxLTAuMjM4MjgtMC44Mzk4NC0wLjIzODI4LTEuNTU4Ni0wLjM1OTM4LTIuMjgxMi0wLjcxODc1LTEuNTU4Ni0wLjQ4MDQ3LTMuMTIxMS0xLjA3ODEtNC41NTg2LTEuODAwOC0zLTEuMzIwMy01Ljc2MTctMi44Nzg5LTguNTE5NS00LjgwMDgtNS4yODEyLTMuODM5OC05Ljk2MDktOC42NDA2LTEzLjMyLTE0LjI4MS0wLjQ4MDQ3LTAuNDgwNDctMi4wMzkxLTQuNjc5Ny0yLjAzOTEtMTIuOTYxIDAtMTYuODAxIDQuNTU4Ni0zOS44NCAxMC40NDEtNjIuNTIgMTEuODc5LTQ1Ljg0IDI3LjQ4LTkzLjQ4IDQyLjYwMi0xNDAuODhsMTYuNjgtNTIuMDc4IDE1Ny41NiAxMTUuMzIgMzYuNjAyIDI2Ljc2MmMtMTQuMDM5IDEwLjMyLTI3LjcxOSAyMC4yODEtNDAuOTIyIDI5Ljg3OXptNDI1LjI4IDgzLjM5OGMtMC4xMjEwOSAxLjkyMTktMC4yMzgyOCAzLjk2MDktMC4zNTkzOCA1Ljg3ODktMC4yMzgyOCAxLjU1ODYtMC42MDE1NiAyLjg3ODktMC43MTg3NSA0LjQ0MTQtMC40ODA0NyAwLjgzOTg0LTAuNjAxNTYgMS45MjE5LTAuODM5ODQgMi41MTk1LTAuMjM4MjggMC4xMjEwOS0wLjM1OTM4IDAuMzU5MzgtMC4zNTkzOCAwLjQ4MDQ3djAuMzU5MzhsLTAuNzE4NzUgMS4wNzgxYy0zLjk2MDkgNi05IDExLjE2LTE1IDE1LTMgMS45MjE5LTYuMTIxMSAzLjQ4MDUtOS4zNTk0IDQuODAwOC0xLjY3OTcgMC42MDE1Ni0zLjM1OTQgMS4xOTkyLTUuMDM5MSAxLjY3OTctMS4wNzgxIDAuMzU5MzgtMS4zMjAzIDAuMjM4MjgtMS40NDE0IDAuMjM4MjgtMC4xMjEwOSAwLTAuMzU5MzggMC0wLjQ4MDQ3IDAuMTIxMDktMi4wMzkxIDAuMzU5MzgtOS44Mzk4LTAuODM5ODQtMTguODQtNC44MDA4LTkuMTIxMS0zLjgzOTgtMTkuMDc4LTguNzYxNy0yOS4yODEtMTQuODc5LTQxLjAzOS0yNC4zNTktODMuMjgxLTU2LjE2LTEyNS4wNC04Ni42NDFsLTQzLjkyMi0zMi4zOThjNzQuNjQxLTU1LjE5OSAxNDUuMDgtMTExIDE4Mi40LTE1Mi41MmwzLjIzODMgMTAuMDc4YzE1LjIzOCA0Ny42NDEgMzAuODQgOTUuMTYgNDQuNTIgMTQyLjA4IDcuMDc4MSAyNC4zNTkgMTMuODAxIDQ4Ljg0IDE4IDcxLjY0MSAxLjkyMTkgMTEuMTYgMy4yMzgzIDIyLjA3OCAzLjIzODMgMzAuOTYxem01MC4wMzktNTk5LjI4YzI1LjMyIDAuNzE4NzUgNTAuNTIgMS44MDA4IDczLjMyIDQuNjc5NyAxMS4wMzkgMS41NTg2IDIxLjcxOSAzLjYwMTYgMjkuNjQxIDYuMjM4MyAxLjY3OTcgMC43MTg3NSAzLjM1OTQgMS40NDE0IDUuMDM5MSAyLjAzOTEgMS4zMjAzIDAuNzE4NzUgMi4yODEyIDEuMzIwMyAzLjQ4MDUgMS44MDA4IDAuNDgwNDcgMC42MDE1NiAxLjE5OTIgMC45NjA5NCAxLjU1ODYgMS4xOTkyIDAgMC4xMjEwOSAwIDAuMjM4MjggMC4xMjEwOSAwLjIzODI4aDAuMjM4MjhsMC43MTg3NSAwLjk2MDk0YzQuMTk5MiA1LjI4MTIgNy4zMjAzIDExLjM5OCA5IDE3Ljg3OSAwLjgzOTg0IDMuMjM4MyAxLjMyMDMgNi42MDE2IDEuNTU4NiA5Ljk2MDl2NS4wMzkxIDEuMzIwM3MtMC4yMzgyOCAwLjEyMTA5LTAuMjM4MjggMC4yMzgyOHYwLjM1OTM4Yy0wLjEyMTA5IDIuMDM5MS02LjQ4MDUgMTIuOTYxLTE3LjI4MSAyMy42NDEtMTAuNjggMTAuOTIyLTI0LjQ4IDIyLjQ0MS0zOC43NjIgMzMuODQtMjguNTU5IDIyLjgwMS01OS43NjIgNDUuNDgtODYuNTIgNjcuMDc4LTI2Ljg3OSAyMS4yMzgtNDkuNDQxIDQxLjY0MS02NC4xOTkgNTkuMzk4bC03NS43MTktMjM2Ljg4aDgwLjc2MmMyNi4wMzkgMC4yMzgyOCA1MS45NjEgMC4zNTkzOCA3Ny4yODEgMS4wNzgxem0tNDYyLjM2LTE3NS4wOGM3LjY3OTctMjMuNTIgMTUuMzU5LTQ3LjAzOSAyMy42NDEtNjkuNjAyIDguMTYwMi0yMi40NDEgMTYuOTIyLTQ0Ljg3OSAyNi42NDEtNjMuMTIxIDQuODAwOC05IDEwLjA3OC0xNi41NTkgMTQuMDM5LTIwLjY0MSAwLjk2MDk0LTEuMDc4MSAxLjkyMTktMi4wMzkxIDIuNTE5NS0yLjI4MTIgMC4zNTkzOC0wLjIzODI4IDAuNjAxNTYtMC40ODA0NyAwLjgzOTg0LTAuODM5ODRoMC40ODA0N2MwLjM1OTM4IDAtMC4yMzgyOC0wLjIzODI4IDAuNzE4NzUtMC40ODA0NyAwLjgzOTg0LTAuMjM4MjggMS41NTg2LTAuNjAxNTYgMi4zOTg0LTAuODM5ODQgMS41NTg2LTAuNjAxNTYgMy4xMjExLTEuMDc4MSA0LjgwMDgtMS40NDE0IDYuNDgwNS0xLjU1ODYgMTMuMzItMS44MDA4IDE5LjgwMS0wLjYwMTU2IDMuMjM4MyAwLjYwMTU2IDYuNDgwNSAxLjQ0MTQgOS42MDE2IDIuNjQwNiAxLjQ0MTQgMC42MDE1NiAwLjcxODc1IDAuNzE4NzUgMS40NDE0IDAuNzE4NzUgMC40ODA0NyAwLjQ4MDQ3IDEuMTk5MiAxLjA3ODEgMS45MjE5IDEuNDQxNCAzLjQ4MDUgMi43NjE3IDguODc4OSAxMC4xOTkgMTMuODAxIDE4LjcxOSA1LjAzOTEgOC4zOTg0IDkuNzE4OCAxOC44NCAxNC4yODEgMjkuMDM5IDkgMjEuMjM4IDE3LjI4MSA0NC4wMzkgMjUuMTk5IDY3LjE5OSAxNS44NCA0Ni4xOTkgMzAuODQgOTMuNzE5IDQ2LjE5OSAxNDFoLTEwNy40LTEzMy4zMmwzMi4yODEtMTAwLjY4em0tNDExLjEyIDIwNS44YzEuMTk5Mi0zLjIzODMgMi42NDA2LTYuMzU5NCA0LjQ0MTQtOS4zNTk0IDAuOTYwOTQtMS40NDE0IDEuOTIxOS0yLjg3ODkgMi44Nzg5LTQuMTk5MiAwLjQ4MDQ3LTAuNjAxNTYgMS4xOTkyLTEuNTU4NiAxLjQ0MTQtMS44MDA4IDAuMjM4MjggMCAwLjIzODI4IDAgMC4zNTkzOC0wLjIzODI4IDAuNjAxNTYtMC45NjA5NCA2LjgzOTgtNC41NTg2IDE1Ljk2MS02LjgzOTggMTguMjM4LTQuOTIxOSA0My4zMi02Ljk2MDkgNjcuOTIyLTguMjgxMiAyNC45NjEtMS4xOTkyIDUwLjY0MS0xLjQ0MTQgNzYuNDQxLTEuNjc5N2gxMDcuNzZjLTI0Ljk2MSA3NS40OC01MC4wMzkgMTUwLjg0LTc1IDIyNi4ybC05MC40OC02Ni45NjFjLTIwLjY0MS0xNS40OC00MS4wMzktMzEuMDc4LTYwLjEyMS00Ni45MjItMTguODQtMTUuNjAyLTM3LjQ0MS0zMi4zOTgtNDgtNDYuODAxLTUuMTYwMi03LjE5OTItNi43MTg4LTEyLjEyMS02LjYwMTYtMTIuNzE5LTAuNDgwNDctNi45NjA5IDAuNjAxNTYtMTQuMDM5IDIuODc4OS0yMC41MnoiLz4KPC9zdmc+Cg==" alt="Built with Spellbook"></a>
</p>

<p align="center">
  <a href="https://axiomantic.github.io/spellbook/"><strong>Documentation</strong></a> ·
  <a href="https://axiomantic.github.io/spellbook/getting-started/installation/"><strong>Getting Started</strong></a> ·
  <a href="https://axiomantic.github.io/spellbook/skills/"><strong>Skills Reference</strong></a>
</p>

## Prerequisites

Install [uv](https://docs.astral.sh/uv/) (fast Python package manager):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Quick Install

One-liner:
```bash
curl -fsSL https://raw.githubusercontent.com/axiomantic/spellbook/main/bootstrap.sh | bash
```

Or manually:
```bash
git clone https://github.com/axiomantic/spellbook.git ~/.local/share/spellbook
cd ~/.local/share/spellbook
uv run install.py
```

**Upgrade:** `cd ~/.local/share/spellbook && git pull && uv run install.py`

**Uninstall:** `uv run ~/.local/share/spellbook/uninstall.py`

## What's Included

### Skills (26 total)

Reusable workflows for structured development:

| Category | Skills | Origin |
|----------|--------|--------|
| **Core Workflow** | [brainstorming], [writing-plans], [executing-plans], [test-driven-development], [debug], [using-git-worktrees], [finishing-a-development-branch] | [superpowers] |
| **Code Quality** | [green-mirage-audit], [fix-tests], [factchecker], [find-dead-code], [receiving-code-review], [requesting-code-review] | mixed |
| **Feature Dev** | [implement-feature], [design-doc-reviewer], [implementation-plan-reviewer], [devils-advocate], [smart-merge] | spellbook |
| **Specialized** | [async-await-patterns], [nim-pr-guide] | spellbook |
| **Meta** | [using-skills], [writing-skills], [subagent-prompting], [instruction-engineering], [dispatching-parallel-agents], [subagent-driven-development] | [superpowers] |

[brainstorming]: https://axiomantic.github.io/spellbook/latest/skills/brainstorming/
[writing-plans]: https://axiomantic.github.io/spellbook/latest/skills/writing-plans/
[executing-plans]: https://axiomantic.github.io/spellbook/latest/skills/executing-plans/
[test-driven-development]: https://axiomantic.github.io/spellbook/latest/skills/test-driven-development/
[debug]: https://axiomantic.github.io/spellbook/latest/skills/debug/
[using-git-worktrees]: https://axiomantic.github.io/spellbook/latest/skills/using-git-worktrees/
[green-mirage-audit]: https://axiomantic.github.io/spellbook/latest/skills/green-mirage-audit/
[fix-tests]: https://axiomantic.github.io/spellbook/latest/skills/fix-tests/
[factchecker]: https://axiomantic.github.io/spellbook/latest/skills/factchecker/
[find-dead-code]: https://axiomantic.github.io/spellbook/latest/skills/find-dead-code/
[receiving-code-review]: https://axiomantic.github.io/spellbook/latest/skills/receiving-code-review/
[requesting-code-review]: https://axiomantic.github.io/spellbook/latest/skills/requesting-code-review/
[implement-feature]: https://axiomantic.github.io/spellbook/latest/skills/implement-feature/
[design-doc-reviewer]: https://axiomantic.github.io/spellbook/latest/skills/design-doc-reviewer/
[implementation-plan-reviewer]: https://axiomantic.github.io/spellbook/latest/skills/implementation-plan-reviewer/
[devils-advocate]: https://axiomantic.github.io/spellbook/latest/skills/devils-advocate/
[smart-merge]: https://axiomantic.github.io/spellbook/latest/skills/smart-merge/
[async-await-patterns]: https://axiomantic.github.io/spellbook/latest/skills/async-await-patterns/
[nim-pr-guide]: https://axiomantic.github.io/spellbook/latest/skills/nim-pr-guide/
[using-skills]: https://axiomantic.github.io/spellbook/latest/skills/using-skills/
[writing-skills]: https://axiomantic.github.io/spellbook/latest/skills/writing-skills/
[subagent-prompting]: https://axiomantic.github.io/spellbook/latest/skills/subagent-prompting/
[instruction-engineering]: https://axiomantic.github.io/spellbook/latest/skills/instruction-engineering/
[dispatching-parallel-agents]: https://axiomantic.github.io/spellbook/latest/skills/dispatching-parallel-agents/
[subagent-driven-development]: https://axiomantic.github.io/spellbook/latest/skills/subagent-driven-development/
[finishing-a-development-branch]: https://axiomantic.github.io/spellbook/latest/skills/finishing-a-development-branch/

### Commands (15 total)

| Command | Description | Origin |
|---------|-------------|--------|
| [/shift-change] | Custom session compaction | spellbook |
| [/distill-session] | Extract knowledge from sessions | spellbook |
| [/simplify] | Code complexity reduction | spellbook |
| [/address-pr-feedback] | Handle PR review comments | spellbook |
| [/move-project] | Relocate projects safely | spellbook |
| [/green-mirage-audit] | Test suite audit | spellbook |
| [/verify] | Verification before completion | [superpowers]* |
| [/systematic-debugging] | Methodical debugging workflow | [superpowers]* |
| [/scientific-debugging] | Hypothesis-driven debugging | spellbook |
| [/brainstorm] | Design exploration | [superpowers] |
| [/write-plan] | Create implementation plan | [superpowers] |
| [/execute-plan] | Execute implementation plan | [superpowers] |
| [/execute-work-packet] | Execute a single work packet with TDD | spellbook |
| [/execute-work-packets-seq] | Execute all packets sequentially | spellbook |
| [/merge-work-packets] | Merge completed packets with QA gates | spellbook |

*\* Converted from skill to command. Originally `verification-before-completion` and `systematic-debugging` skills in superpowers.*

[/shift-change]: https://axiomantic.github.io/spellbook/latest/commands/shift-change/
[/distill-session]: https://axiomantic.github.io/spellbook/latest/commands/distill-session/
[/simplify]: https://axiomantic.github.io/spellbook/latest/commands/simplify/
[/address-pr-feedback]: https://axiomantic.github.io/spellbook/latest/commands/address-pr-feedback/
[/move-project]: https://axiomantic.github.io/spellbook/latest/commands/move-project/
[/green-mirage-audit]: https://axiomantic.github.io/spellbook/latest/commands/green-mirage-audit/
[/verify]: https://axiomantic.github.io/spellbook/latest/commands/verify/
[/systematic-debugging]: https://axiomantic.github.io/spellbook/latest/commands/systematic-debugging/
[/scientific-debugging]: https://axiomantic.github.io/spellbook/latest/commands/scientific-debugging/
[/brainstorm]: https://axiomantic.github.io/spellbook/latest/commands/brainstorm/
[/write-plan]: https://axiomantic.github.io/spellbook/latest/commands/write-plan/
[/execute-plan]: https://axiomantic.github.io/spellbook/latest/commands/execute-plan/
[/execute-work-packet]: https://axiomantic.github.io/spellbook/latest/commands/execute-work-packet/
[/execute-work-packets-seq]: https://axiomantic.github.io/spellbook/latest/commands/execute-work-packets-seq/
[/merge-work-packets]: https://axiomantic.github.io/spellbook/latest/commands/merge-work-packets/

### Agents (1 total)

| Agent | Description | Origin |
|-------|-------------|--------|
| [code-reviewer] | Specialized code review | [superpowers] |

[code-reviewer]: https://axiomantic.github.io/spellbook/latest/agents/code-reviewer/
[superpowers]: https://github.com/obra/superpowers

## Platform Support

| Platform | Status | Details |
|----------|--------|---------|
| Claude Code | Full | Native skills + MCP server |
| OpenCode | Full | Skill symlinks |
| Codex | Full | Bootstrap + MCP |
| Gemini CLI | Partial | MCP server + context file |
| Crush | Full | Native Agent Skills + MCP server |

### Autonomous Mode

> [!CAUTION]
> **Autonomous mode gives your AI assistant full control of your system.**
>
> It can execute arbitrary commands, write and delete files, install packages, and make irreversible changes - all without asking permission. A misconfigured workflow or hallucinated command can corrupt your project, expose secrets, or worse.
>
> **Only enable autonomous mode when:**
> - Working in an isolated environment (container, VM, disposable branch)
> - You have tested the workflow manually first
> - You have backups and version control
> - You understand what each platform's flag actually permits
>
> **You are responsible for what it does.** Review platform documentation before enabling.

For fully automated workflows (no permission prompts), each platform has its own flag:

| Platform | Command | What it does |
|----------|---------|--------------|
| Claude Code | `claude --dangerously-skip-permissions` | Skips all permission prompts |
| Gemini CLI | `gemini --yolo` | Enables autonomous execution |
| OpenCode | `opencode --prompt "task"` | Non-interactive mode auto-approves all |
| Codex | `codex --full-auto` | Workspace writes + on-request approval |
| Codex | `codex --yolo` | Bypasses all approvals and sandbox |
| Crush | `crush --yolo` | Bypasses all permission prompts |

Without autonomous mode, you'll be prompted to approve each file write, command execution, etc. The workflows still function, but require manual approval at each step.

See platform documentation for details: [Claude Code](https://docs.anthropic.com/en/docs/claude-code), [OpenCode](https://opencode.ai/docs/permissions/), [Codex](https://developers.openai.com/codex/cli/reference/), [Gemini CLI](https://github.com/google-gemini/gemini-cli), [Crush](https://github.com/charmbracelet/crush).

## Playbooks

Real-world usage patterns with example transcripts.

### Large Feature with Context Exhaustion

When implementing a complex feature, context can fill up before work completes. The workflow handles this gracefully.

```
╭─────────────────────────────────────────────────────────────────────────────╮
│ > Implement webhook delivery with retry logic and dead letter queue         │
╰─────────────────────────────────────────────────────────────────────────────╯

⏺ Skill(implement-feature)

  I'll help you implement the webhook delivery system. Let me first
  understand the current codebase architecture and gather requirements.

⏺ Task(Explore)

  ⎿ Found: src/events/, src/queue/, src/models/Webhook.ts
    Current event system uses Redis pub/sub. No existing retry logic.

⏺ AskUserQuestion

  ╭─────────────────────────────────────────────────────────────────────────╮
  │ Retry strategy                                                          │
  ├─────────────────────────────────────────────────────────────────────────┤
  │ ○ Exponential backoff (Recommended)                                     │
  │ ○ Fixed interval                                                        │
  │ ○ Linear backoff                                                        │
  ╰─────────────────────────────────────────────────────────────────────────╯

> Exponential backoff

⏺ Writing implementation plan to:
  ~/.local/spellbook/docs/Users-me-myproject/plans/webhook-delivery-impl.md

  ...

⏺ Task(Backend API) [in background]
  ⎿ Implementing retry queue with exponential backoff...

⏺ Task(Worker Service) [in background]
  ⎿ Building delivery worker with circuit breaker...

⏺ Task(Dead Letter Queue) [in background]
  ⎿ Setting up DLQ with monitoring hooks...

  ...

⏺ Task Output(non-blocking) ad8b5e4
  ⎿ Task is still running…

╭─────────────────────────────────────────────────────────────────────────────╮
│ ⚠ Context low · Run /compact to compact & continue                         │
╰─────────────────────────────────────────────────────────────────────────────╯
```

When context runs low, name and distill the session for later:

```
╭─────────────────────────────────────────────────────────────────────────────╮
│ > /rename-session webhook-delivery                                          │
╰─────────────────────────────────────────────────────────────────────────────╯

⏺ Session renamed to: webhook-delivery

╭─────────────────────────────────────────────────────────────────────────────╮
│ > /distill-session webhook-delivery                                         │
╰─────────────────────────────────────────────────────────────────────────────╯

⏺ Skill(distill-session)

  Found session: webhook-delivery
  Processing 847 messages across 3 compact boundaries...

  ⏺ Task(Chunk 1 Summary) [in background]
  ⏺ Task(Chunk 2 Summary) [in background]
  ⏺ Task(Chunk 3 Summary) [in background]

  Synthesizing summaries...

  ✓ Distilled session saved to:
    ~/.local/spellbook/distilled/Users-me-myproject/webhook-delivery-20260106-143022.md

  To continue in a new session:
    1. Start new Claude Code session
    2. Type: "continue work from ~/.local/spellbook/distilled/Users-me-myproject/
              webhook-delivery-20260106-143022.md"
```

Start fresh and resume exactly where you left off:

```
╭─────────────────────────────────────────────────────────────────────────────╮
│ > /clear                                                                    │
╰─────────────────────────────────────────────────────────────────────────────╯

╭─────────────────────────────────────────────────────────────────────────────╮
│ > continue work from ~/.local/spellbook/distilled/Users-me-myproject/       │
│   webhook-delivery-20260106-143022.md                                       │
╰─────────────────────────────────────────────────────────────────────────────╯

⏺ Read(~/.local/spellbook/distilled/.../webhook-delivery-20260106-143022.md)

⏺ SECTION 0: MANDATORY FIRST ACTIONS

  Executing restoration sequence...

⏺ Skill(implement-feature, --resume-from Phase3.Task4)

  Resuming webhook delivery implementation.

  Prior work completed:
  ✓ Design approved (exponential backoff, 5 retries, 1hr max)
  ✓ Database migrations for delivery_attempts table
  ✓ Retry queue infrastructure
  ○ Worker service (in progress - 60% complete)
  ○ Dead letter queue
  ○ Monitoring dashboard

⏺ Read(~/.local/spellbook/docs/.../webhook-delivery-impl.md)

  Continuing from Phase 3, Task 4: Complete worker service...
```

### Test Suite Audit and Remediation

Discover tests that pass but don't actually verify behavior, then fix them.

```
╭─────────────────────────────────────────────────────────────────────────────╮
│ > /green-mirage-audit                                                       │
╰─────────────────────────────────────────────────────────────────────────────╯

⏺ Skill(green-mirage-audit)

  Analyzing test suite: tests/**/*.test.ts
  Found 247 test cases across 34 files.

  ⏺ Task(Analyze auth tests) [in background]
  ⏺ Task(Analyze api tests) [in background]
  ⏺ Task(Analyze util tests) [in background]

  ...

  ✓ Audit complete. Report saved to:
    ~/.local/spellbook/docs/Users-me-myproject/audits/green-mirage-audit-20260106-091522.md

  Summary:
  ┌─────────────────────────────────────────────────────────────────────────┐
  │ SOLID (actually verify behavior)      │ 189 tests (76%)                │
  │ GREEN MIRAGE (false confidence)       │  58 tests (24%)                │
  │                                       │                                │
  │ Critical issues:                      │                                │
  │   • 12 tests mock the thing tested    │                                │
  │   • 8 tests have no meaningful assert │                                │
  │   • 38 tests check implementation     │                                │
  └─────────────────────────────────────────────────────────────────────────┘

╭─────────────────────────────────────────────────────────────────────────────╮
│ > Fix the critical issues from the audit                                    │
╰─────────────────────────────────────────────────────────────────────────────╯

⏺ Skill(fix-tests)

  Loading audit report...
  Found 58 tests requiring remediation.

  Starting with highest-impact fixes (mocked implementations)...

⏺ Read(tests/auth/login.test.ts)

⏺ Edit(tests/auth/login.test.ts)

  - jest.mock('../services/AuthService')  // Mocks the thing we're testing!
  + // Test actual AuthService behavior with test database
```

### Parallel Worktree Development

Split work across isolated branches, merge when complete.

```
╭─────────────────────────────────────────────────────────────────────────────╮
│ > Let's design a new notification system                                    │
╰─────────────────────────────────────────────────────────────────────────────╯

⏺ Skill(brainstorming)

  I'll explore the notification system requirements with you.

  ...design discussion, interface contracts established...

  Design document saved to:
    ~/.local/spellbook/docs/Users-me-myproject/plans/notifications-design.md

╭─────────────────────────────────────────────────────────────────────────────╮
│ > Set up worktrees to implement this in parallel                            │
╰─────────────────────────────────────────────────────────────────────────────╯

⏺ Skill(using-git-worktrees)

  Creating isolated worktrees for parallel development:

  ✓ .worktrees/notif-backend     (branch: feature/notif-backend)
  ✓ .worktrees/notif-frontend    (branch: feature/notif-frontend)
  ✓ .worktrees/notif-tests       (branch: feature/notif-tests)

  Interface contracts copied to each worktree.

╭─────────────────────────────────────────────────────────────────────────────╮
│ > Work on all three tracks                                                  │
╰─────────────────────────────────────────────────────────────────────────────╯

⏺ Task(.worktrees/notif-backend) [in background]
  ⎿ Implementing notification service, queue, templates...

⏺ Task(.worktrees/notif-frontend) [in background]
  ⎿ Building NotificationCenter component, hooks, real-time updates...

⏺ Task(.worktrees/notif-tests) [in background]
  ⎿ Writing integration tests against interface contracts...

  ...

╭─────────────────────────────────────────────────────────────────────────────╮
│ > Merge the worktrees back together                                         │
╰─────────────────────────────────────────────────────────────────────────────╯

⏺ Skill(smart-merge)

  Analyzing 3 worktrees for merge:

  Step 1: Dependency analysis
    notif-tests depends on: notif-backend, notif-frontend
    notif-frontend depends on: notif-backend (types only)
    notif-backend: no dependencies (merge first)

  Step 2: 3-way diff analysis
    No conflicts detected. Interface contracts honored.

  Step 3: Merge sequence
    ✓ Merged notif-backend → main
    ✓ Merged notif-frontend → main
    ✓ Merged notif-tests → main

  Step 4: Validation
    ✓ All tests pass
    ✓ Type check clean
    ✓ Worktrees cleaned up

  Ready to push or create PR.
```

### Cross-Assistant Handoff

Move work between different AI coding assistants without losing context.

```
# In Cursor, context is running low on a complex refactor...

╭─────────────────────────────────────────────────────────────────────────────╮
│ > /distill-session                                                          │
╰─────────────────────────────────────────────────────────────────────────────╯

⏺ Session distilled to:
  ~/.local/spellbook/distilled/Users-me-myproject/refactor-auth-20260106-162033.md

# Open Claude Code CLI in terminal...

╭─────────────────────────────────────────────────────────────────────────────╮
│ > continue work from ~/.local/spellbook/distilled/Users-me-myproject/       │
│   refactor-auth-20260106-162033.md                                          │
╰─────────────────────────────────────────────────────────────────────────────╯

⏺ Loading distilled session...

  Context restored:
  • Refactoring auth from session-based to JWT
  • 4 of 7 services migrated
  • Current: PaymentService (blocked on token refresh)
  • Decision: Chose sliding window refresh (not fixed expiry)

  Continuing with PaymentService migration...
```

The distilled file compresses ~50K tokens of conversation into ~3K words of actionable context.

## Recommended Companion Tools

These tools are not necessary but contribute to better development workflows with coding assistants.

### Heads Up Claude

Statusline for Claude Code CLI showing token usage and conversation stats. Helps you track how much context you have left and how much of your subscription quota you have used.

```bash
git clone https://github.com/elijahr/heads-up-claude.git ~/Development/heads-up-claude
cd ~/Development/heads-up-claude && ./install.sh
```

### MCP Language Server

LSP integration for semantic code navigation, refactoring, and more.

```bash
git clone https://github.com/axiomantic/mcp-language-server.git ~/Development/mcp-language-server
cd ~/Development/mcp-language-server && go build
```

## Development

### Serve Documentation Locally

```bash
cd ~/.local/share/spellbook
uvx mkdocs serve
```

Then open http://127.0.0.1:8000

### Run MCP Server Directly

```bash
cd ~/.local/share/spellbook/spellbook_mcp
uv run server.py
```

## Documentation

Full documentation available at **[axiomantic.github.io/spellbook](https://axiomantic.github.io/spellbook/)**

- [Installation Guide](https://axiomantic.github.io/spellbook/getting-started/installation/)
- [Platform Support](https://axiomantic.github.io/spellbook/getting-started/platforms/)
- [Skills Reference](https://axiomantic.github.io/spellbook/skills/)
- [Commands Reference](https://axiomantic.github.io/spellbook/commands/)
- [Architecture](https://axiomantic.github.io/spellbook/reference/architecture/)
- [Contributing](https://axiomantic.github.io/spellbook/reference/contributing/)

## Contributing

**Want Spellbook on your coding assistant?** e.g. Cursor, Kline, Roo, Kilo, Continue, GitHub Copilot, etc. If your assistant supports MCP but isn't listed in Platform Support, you can port it yourself:

See the [**Porting Guide**](docs/contributing/porting-to-your-assistant.md) - A self-contained prompt you paste into your coding assistant to have it add Spellbook support for itself and submit a PR back to this repo. We appreciate your contributions!

## Acknowledgments

Spellbook includes many skills, commands, agents, and hooks from [obra/superpowers](https://github.com/obra/superpowers) by Jesse Vincent. These workflow patterns (brainstorming, planning, execution, git worktrees, TDD, debugging) are a core part of spellbook's development methodology.

See [THIRD-PARTY-NOTICES](THIRD-PARTY-NOTICES) for full attribution and license details.

## Attribution

Built something with Spellbook? We'd love to see it! Add this badge to your project:

```markdown
[![Built with Spellbook](https://img.shields.io/badge/Built%20with-Spellbook-6B21A8?style=for-the-badge&logo=data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiPz4KPHN2ZyB3aWR0aD0iMTIwMHB0IiBoZWlnaHQ9IjEyMDBwdCIgdmVyc2lvbj0iMS4xIiB2aWV3Qm94PSIwIDAgMTIwMCAxMjAwIiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciPgogPHBhdGggZmlsbD0iI0ZGRiIgZD0ibTI4LjQ0MSA1MDkuMjhjMC42MDE1NiA1LjAzOTEgMi4yODEyIDkuMzU5NCAzLjcxODggMTMuODAxIDMuMTIxMSA4LjY0MDYgNy4zMjAzIDE2LjA3OCAxMS43NjIgMjIuNjggOC44Nzg5IDEzLjA3OCAxOC42MDIgMjMuODc5IDI4LjU1OSAzMy40OCAxOS44MDEgMTkuNDQxIDQwLjMyIDM1LjY0MSA2MC44NCA1MS43MTkgNDEuMTYgMzEuNjggODIuNTU5IDYxLjU1OSAxMjMuNzIgOTEuOTIybDIzLjY0MSAxNy4yODFjLTUuMTYwMiAxNS42MDItMTAuNDQxIDMxLjMyLTE1LjYwMiA0Ny4wMzktMTYuMDc4IDQ4LjQ4LTMyLjY0MSA5Ni43MTktNDcuNjQxIDE0Ni44OC03LjMyMDMgMjUuMTk5LTE0LjUyIDUwLjc2Mi0xOS4wNzggNzkuMzItMS45MjE5IDE0LjUyLTMuNjAxNiAyOS43NjItMS41NTg2IDQ4IDEuMTk5MiA5LjEyMTEgMy4yMzgzIDE5LjA3OCA3LjkyMTkgMjkuMTZsMy43MTg4IDcuNTU4NmMxLjMyMDMgMi42NDA2IDIuMzk4NCAzLjk2MDkgMy42MDE2IDYgMi4zOTg0IDMuNzE4OCA1LjAzOTEgNy4zMjAzIDcuOTIxOSAxMC44MDEgMTEuMjgxIDEzLjkyMiAyNS40NDEgMjUuNTU5IDQxLjM5OCAzMy44NCA4LjAzOTEgNC4xOTkyIDE2LjQ0MSA3LjU1ODYgMjUuMDc4IDkuOTYwOSAxLjkyMTkgMC42MDE1NiA0LjY3OTcgMS4xOTkyIDcuNTU4NiAxLjY3OTdsOC41MTk1IDEuMzIwM2M1LjUxOTUgMC40ODA0NyAxMC42OCAwLjIzODI4IDE2LjA3OCAwLjIzODI4IDIwLjM5OC0xLjY3OTcgMzUuNTItNy44MDA4IDQ5LjQ0MS0xMy42OCAxNC4wMzktNiAyNi4xNi0xMi44NCAzOC4xNi0xOS42OCA0Ni45MjItMjcuODQgODguMDc4LTU3Ljk2MSAxMzAuMDgtODcuMzU5IDI0Ljk2MS0xNy42NDEgNTEuNjAyLTM2LjYwMiA3OC43MTktNTYuMDM5bDEzLjA3OCA5LjYwMTZjNDEuMjgxIDMwLjEyMSA4Mi4xOTkgNjAuNjAyIDEyNC44IDkwLjIzOCAyMS40OCAxNC43NjIgNDMuMDc4IDI5LjM5OCA2Ny4zMiA0Mi40OCAxMi4xMjEgNi40ODA1IDI1LjA3OCAxMi42MDIgMzkuOTYxIDE3LjI4MSAzLjk2MDkgMC45NjA5NCA3LjU1ODYgMi4xNjAyIDExLjc2MiAzIDQuMzIwMyAwLjYwMTU2IDguMzk4NCAxLjQ0MTQgMTIuODQgMS42Nzk3IDQuNjc5NyAwIDkuMTIxMSAwLjQ4MDQ3IDE0LjAzOS0wLjM1OTM4IDQuODAwOC0wLjcxODc1IDEwLjA3OC0xLjU1ODYgMTMuNjgtMi42NDA2IDE1LjcxOS00LjQ0MTQgMzAuNDgtMTIuMjM4IDQzLjA3OC0yMi42OCA2LjIzODMtNS4xNjAyIDEyLTExLjAzOSAxNy4xNi0xNy4zOThzOS4zNTk0LTEyLjcxOSAxMy42OC0yMi4xOTljNy41NTg2LTE3Ljg3OSA3LjY3OTctMzQuNDQxIDcuMDc4MS00OS4wNzgtMC44Mzk4NC0xNC43NjItMy0yOC41NTktNS42NDA2LTQxLjc2Mi0xMS4xNi01Mi42OC0yNy40OC0xMDEuMTYtNDIuNzE5LTE1MC4xMmwtMzUuMzk4LTExMC4yOGMyMS4xMjEtNi4yMzgzIDQ5LjgwMS0yMy4xNiA4MS44NC00NC43NjIgMjguNTU5LTE5LjE5OSA1OS42NDEtNDIuMzU5IDkwLTY3LjE5OSAxNS4xMjEtMTIuNDggMzAtMjUuNDQxIDQ0LjE2LTM5LjIzOCAxMy45MjItMTMuOTIyIDI3LjQ4LTI4LjY4IDM3LjU1OS00OC4xMjEgMS45MjE5LTMuODM5OCAzLjgzOTgtNy42Nzk3IDUuMTYwMi0xMi4yMzhsMi4xNjAyLTYuNjAxNiAxLjMyMDMtNy4xOTkyYzAuOTYwOTQtNS4xNjAyIDEuMDc4MS05LjEyMTEgMS4xOTkyLTEzLjE5OSAwLTQuMDc4MSAwLTguMTYwMi0wLjQ4MDQ3LTEyLjIzOC0xLjQ0MTQtMTYuMzItNi4xMjExLTMyLjM5OC0xMy44MDEtNDYuODAxLTMuODM5OC03LjE5OTItOC4zOTg0LTE0LjE2LTEzLjY4LTIwLjM5OC0zLjIzODMtMy40ODA1LTYuODM5OC03LjMyMDMtMTAuNDQxLTEwLjMyLTMuNzE4OC0yLjY0MDYtNy41NTg2LTUuODc4OS0xMS4zOTgtNy44MDA4LTE1LjQ4LTguODc4OS0zMC4yMzgtMTIuODQtNDQuMjgxLTE1LjcxOS0yOC4xOTktNS43NjE3LTU0LjM1OS02Ljk2MDktODAuNTItOC4yODEyLTI2LjE2LTEuMDc4MS01MS44NC0xLjQ0MTQtNzcuNTItMS41NTg2aC0xMjYuOTZsLTM1LjY0MS0xMTIuMDhjLTcuOTIxOS0yNC4zNTktMTUuODQtNDguODQtMjQuNDgtNzMuNDQxLTguNzYxNy0yNC42MDItMTcuNzYyLTQ5LjE5OS0zMC4xMjEtNzQuMTYtNi4yMzgzLTEyLjQ4LTEzLjE5OS0yNS4wNzgtMjMuNjQxLTM3LjgwMS01LjE2MDItNi4yMzgzLTExLjM5OC0xMi40OC0xOS4zMi0xOC0zLjYwMTYtMi44Nzg5LTguNTE5NS01LjAzOTEtMTIuODQtNy4zMjAzLTQuMTk5Mi0xLjkyMTktNy44MDA4LTMuMTIxMS0xMS44NzktNC40NDE0LTE1Ljg0LTUuMDM5MS0zMi43NjItNi42MDE2LTQ5LjE5OS00LjgwMDgtMTYuNTU5IDIuMjgxMi0zMi4wMzkgNS43NjE3LTQ5LjE5OSAxOC0xNS4xMjEgMTEuNTItMjQuMTIxIDI0LjcxOS0zMS45MjIgMzcuMDc4LTcuNTU4NiAxMi42MDItMTMuNDQxIDI0Ljk2MS0xOS4wNzggMzcuNDQxLTEwLjkyMiAyNC43MTktMTkuNjggNDkuMTk5LTI4LjMyIDczLjY4LTE4LjM1OSA1NS4xOTktMzYuNjAyIDExMC40LTU0Ljk2MSAxNjUuNDhoLTk1Ljg3OWMtNTEuMzU5IDAuNDgwNDctMTAyLjM2LTAuMjM4MjgtMTU2LjI0IDUuMjgxMi0xMy40NDEgMS4zMjAzLTI3LjM1OSAzLjcxODgtNDEuNzYyIDcuMzIwMy0xNC4yODEgMy44Mzk4LTMwLjEyMSA5LjIzODMtNDUuMjM4IDIxLjk2MS0zLjQ4MDUgMy4zNTk0LTcuNTU4NiA3LjMyMDMtMTAuMDc4IDEwLjQ0MS0yLjY0MDYgMy4yMzgzLTUuMDM5MSA2LjYwMTYtNy4zMjAzIDkuOTYwOS00LjU1ODYgNi45NjA5LTguMjgxMiAxNC4yODEtMTEuMjgxIDIxLjk2MS02IDE1LjM1OS05IDMxLjkyMi04LjUxOTUgNDguMzU5bDAuMzU5MzggNi4yMzgzIDEuMDc4MSA3LjMyMDN6bTcxNi42NC02NS42NDEgNjguNjQxIDIxMyAyNS4wNzggNzcuODc5Yy01NCAyMS42MDItMTQ4LjMyIDg3LjQ4LTIzOC42OCAxNTNsLTguMzk4NC02LjEyMTEtMjIyLjEyLTE2My42OCA4Ny44NC0yNzQuMzJoMTI3LjJsMTYwLjU2IDAuMzU5Mzd6bS0yNDUuMDQgNTE2Ljk2Yy00MC4zMiAyOS4yODEtODAuNTIgNTkuMTYtMTIwLjM2IDg1LjA3OC0xOS42OCAxMi43MTktNDAuMTk5IDI0Ljg0LTU2LjM5OCAzMC4zNTktNy45MjE5IDIuODc4OS0xMy42OCAzLTEzLjkyMiAyLjc2MTdoLTAuMjM4MjhjLTAuMjM4MjggMC0wLjcxODc1LTAuMjM4MjgtMS4wNzgxLTAuMjM4MjgtMC44Mzk4NC0wLjIzODI4LTEuNTU4Ni0wLjM1OTM4LTIuMjgxMi0wLjcxODc1LTEuNTU4Ni0wLjQ4MDQ3LTMuMTIxMS0xLjA3ODEtNC41NTg2LTEuODAwOC0zLTEuMzIwMy01Ljc2MTctMi44Nzg5LTguNTE5NS00LjgwMDgtNS4yODEyLTMuODM5OC05Ljk2MDktOC42NDA2LTEzLjMyLTE0LjI4MS0wLjQ4MDQ3LTAuNDgwNDctMi4wMzkxLTQuNjc5Ny0yLjAzOTEtMTIuOTYxIDAtMTYuODAxIDQuNTU4Ni0zOS44NCAxMC40NDEtNjIuNTIgMTEuODc5LTQ1Ljg0IDI3LjQ4LTkzLjQ4IDQyLjYwMi0xNDAuODhsMTYuNjgtNTIuMDc4IDE1Ny41NiAxMTUuMzIgMzYuNjAyIDI2Ljc2MmMtMTQuMDM5IDEwLjMyLTI3LjcxOSAyMC4yODEtNDAuOTIyIDI5Ljg3OXptNDI1LjI4IDgzLjM5OGMtMC4xMjEwOSAxLjkyMTktMC4yMzgyOCAzLjk2MDktMC4zNTkzOCA1Ljg3ODktMC4yMzgyOCAxLjU1ODYtMC42MDE1NiAyLjg3ODktMC43MTg3NSA0LjQ0MTQtMC40ODA0NyAwLjgzOTg0LTAuNjAxNTYgMS45MjE5LTAuODM5ODQgMi41MTk1LTAuMjM4MjggMC4xMjEwOS0wLjM1OTM4IDAuMzU5MzgtMC4zNTkzOCAwLjQ4MDQ3djAuMzU5MzhsLTAuNzE4NzUgMS4wNzgxYy0zLjk2MDkgNi05IDExLjE2LTE1IDE1LTMgMS45MjE5LTYuMTIxMSAzLjQ4MDUtOS4zNTk0IDQuODAwOC0xLjY3OTcgMC42MDE1Ni0zLjM1OTQgMS4xOTkyLTUuMDM5MSAxLjY3OTctMS4wNzgxIDAuMzU5MzgtMS4zMjAzIDAuMjM4MjgtMS40NDE0IDAuMjM4MjgtMC4xMjEwOSAwLTAuMzU5MzggMC0wLjQ4MDQ3IDAuMTIxMDktMi4wMzkxIDAuMzU5MzgtOS44Mzk4LTAuODM5ODQtMTguODQtNC44MDA4LTkuMTIxMS0zLjgzOTgtMTkuMDc4LTguNzYxNy0yOS4yODEtMTQuODc5LTQxLjAzOS0yNC4zNTktODMuMjgxLTU2LjE2LTEyNS4wNC04Ni42NDFsLTQzLjkyMi0zMi4zOThjNzQuNjQxLTU1LjE5OSAxNDUuMDgtMTExIDE4Mi40LTE1Mi41MmwzLjIzODMgMTAuMDc4YzE1LjIzOCA0Ny42NDEgMzAuODQgOTUuMTYgNDQuNTIgMTQyLjA4IDcuMDc4MSAyNC4zNTkgMTMuODAxIDQ4Ljg0IDE4IDcxLjY0MSAxLjkyMTkgMTEuMTYgMy4yMzgzIDIyLjA3OCAzLjIzODMgMzAuOTYxem01MC4wMzktNTk5LjI4YzI1LjMyIDAuNzE4NzUgNTAuNTIgMS44MDA4IDczLjMyIDQuNjc5NyAxMS4wMzkgMS41NTg2IDIxLjcxOSAzLjYwMTYgMjkuNjQxIDYuMjM4MyAxLjY3OTcgMC43MTg3NSAzLjM1OTQgMS40NDE0IDUuMDM5MSAyLjAzOTEgMS4zMjAzIDAuNzE4NzUgMi4yODEyIDEuMzIwMyAzLjQ4MDUgMS44MDA4IDAuNDgwNDcgMC42MDE1NiAxLjE5OTIgMC45NjA5NCAxLjU1ODYgMS4xOTkyIDAgMC4xMjEwOSAwIDAuMjM4MjggMC4xMjEwOSAwLjIzODI4aDAuMjM4MjhsMC43MTg3NSAwLjk2MDk0YzQuMTk5MiA1LjI4MTIgNy4zMjAzIDExLjM5OCA5IDE3Ljg3OSAwLjgzOTg0IDMuMjM4MyAxLjMyMDMgNi42MDE2IDEuNTU4NiA5Ljk2MDl2NS4wMzkxIDEuMzIwM3MtMC4yMzgyOCAwLjEyMTA5LTAuMjM4MjggMC4yMzgyOHYwLjM1OTM4Yy0wLjEyMTA5IDIuMDM5MS02LjQ4MDUgMTIuOTYxLTE3LjI4MSAyMy42NDEtMTAuNjggMTAuOTIyLTI0LjQ4IDIyLjQ0MS0zOC43NjIgMzMuODQtMjguNTU5IDIyLjgwMS01OS43NjIgNDUuNDgtODYuNTIgNjcuMDc4LTI2Ljg3OSAyMS4yMzgtNDkuNDQxIDQxLjY0MS02NC4xOTkgNTkuMzk4bC03NS43MTktMjM2Ljg4aDgwLjc2MmMyNi4wMzkgMC4yMzgyOCA1MS45NjEgMC4zNTkzOCA3Ny4yODEgMS4wNzgxem0tNDYyLjM2LTE3NS4wOGM3LjY3OTctMjMuNTIgMTUuMzU5LTQ3LjAzOSAyMy42NDEtNjkuNjAyIDguMTYwMi0yMi40NDEgMTYuOTIyLTQ0Ljg3OSAyNi42NDEtNjMuMTIxIDQuODAwOC05IDEwLjA3OC0xNi41NTkgMTQuMDM5LTIwLjY0MSAwLjk2MDk0LTEuMDc4MSAxLjkyMTktMi4wMzkxIDIuNTE5NS0yLjI4MTIgMC4zNTkzOC0wLjIzODI4IDAuNjAxNTYtMC40ODA0NyAwLjgzOTg0LTAuODM5ODRoMC40ODA0N2MwLjM1OTM4IDAtMC4yMzgyOC0wLjIzODI4IDAuNzE4NzUtMC40ODA0NyAwLjgzOTg0LTAuMjM4MjggMS41NTg2LTAuNjAxNTYgMi4zOTg0LTAuODM5ODQgMS41NTg2LTAuNjAxNTYgMy4xMjExLTEuMDc4MSA0LjgwMDgtMS40NDE0IDYuNDgwNS0xLjU1ODYgMTMuMzItMS44MDA4IDE5LjgwMS0wLjYwMTU2IDMuMjM4MyAwLjYwMTU2IDYuNDgwNSAxLjQ0MTQgOS42MDE2IDIuNjQwNiAxLjQ0MTQgMC42MDE1NiAwLjcxODc1IDAuNzE4NzUgMS40NDE0IDAuNzE4NzUgMC40ODA0NyAwLjQ4MDQ3IDEuMTk5MiAxLjA3ODEgMS45MjE5IDEuNDQxNCAzLjQ4MDUgMi43NjE3IDguODc4OSAxMC4xOTkgMTMuODAxIDE4LjcxOSA1LjAzOTEgOC4zOTg0IDkuNzE4OCAxOC44NCAxNC4yODEgMjkuMDM5IDkgMjEuMjM4IDE3LjI4MSA0NC4wMzkgMjUuMTk5IDY3LjE5OSAxNS44NCA0Ni4xOTkgMzAuODQgOTMuNzE5IDQ2LjE5OSAxNDFoLTEwNy40LTEzMy4zMmwzMi4yODEtMTAwLjY4em0tNDExLjEyIDIwNS44YzEuMTk5Mi0zLjIzODMgMi42NDA2LTYuMzU5NCA0LjQ0MTQtOS4zNTk0IDAuOTYwOTQtMS40NDE0IDEuOTIxOS0yLjg3ODkgMi44Nzg5LTQuMTk5MiAwLjQ4MDQ3LTAuNjAxNTYgMS4xOTkyLTEuNTU4NiAxLjQ0MTQtMS44MDA4IDAuMjM4MjggMCAwLjIzODI4IDAgMC4zNTkzOC0wLjIzODI4IDAuNjAxNTYtMC45NjA5NCA2LjgzOTgtNC41NTg2IDE1Ljk2MS02LjgzOTggMTguMjM4LTQuOTIxOSA0My4zMi02Ljk2MDkgNjcuOTIyLTguMjgxMiAyNC45NjEtMS4xOTkyIDUwLjY0MS0xLjQ0MTQgNzYuNDQxLTEuNjc5N2gxMDcuNzZjLTI0Ljk2MSA3NS40OC01MC4wMzkgMTUwLjg0LTc1IDIyNi4ybC05MC40OC02Ni45NjFjLTIwLjY0MS0xNS40OC00MS4wMzktMzEuMDc4LTYwLjEyMS00Ni45MjItMTguODQtMTUuNjAyLTM3LjQ0MS0zMi4zOTgtNDgtNDYuODAxLTUuMTYwMi03LjE5OTItNi43MTg4LTEyLjEyMS02LjYwMTYtMTIuNzE5LTAuNDgwNDctNi45NjA5IDAuNjAxNTYtMTQuMDM5IDIuODc4OS0yMC41MnoiLz4KPC9zdmc+Cg==)](https://github.com/axiomantic/spellbook)
```

## License

MIT License - See [LICENSE](LICENSE) for details.
