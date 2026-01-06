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
  - [Workflow Recipes](#workflow-recipes)
    - [End-to-End Feature Implementation](#end-to-end-feature-implementation)
    - [Work Packets for Large Features](#work-packets-for-large-features)
    - [Session Handoff Between Assistants](#session-handoff-between-assistants)
    - [Using Skills](#using-skills)
    - [Parallel Worktree Development](#parallel-worktree-development)
    - [Audit Test Quality](#audit-test-quality)
    - [Find Past Patterns](#find-past-patterns)
    - [Create Custom Skills](#create-custom-skills)
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
  For Claude Code, OpenCode, Codex, and Gemini CLI.
</p>

<p align="center">
  <a href="https://github.com/axiomantic/spellbook/blob/main/LICENSE"><img src="https://img.shields.io/github/license/axiomantic/spellbook?style=flat-square" alt="License"></a>
  <a href="https://github.com/axiomantic/spellbook/stargazers"><img src="https://img.shields.io/github/stars/axiomantic/spellbook?style=flat-square" alt="Stars"></a>
  <a href="https://github.com/axiomantic/spellbook/issues"><img src="https://img.shields.io/github/issues/axiomantic/spellbook?style=flat-square" alt="Issues"></a>
  <a href="https://axiomantic.github.io/spellbook/"><img src="https://img.shields.io/badge/docs-GitHub%20Pages-blue?style=flat-square" alt="Documentation"></a>
</p>

<p align="center">
  <a href="https://github.com/axiomantic/spellbook"><img src="https://img.shields.io/badge/Built%20with-Spellbook-6B21A8?style=flat-square&logo=data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiPz4KPHN2ZyB3aWR0aD0iMTIwMHB0IiBoZWlnaHQ9IjEyMDBwdCIgdmVyc2lvbj0iMS4xIiB2aWV3Qm94PSIwIDAgMTIwMCAxMjAwIiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciPgogPHBhdGggZmlsbD0iI0ZGRiIgZD0ibTI4LjQ0MSA1MDkuMjhjMC42MDE1NiA1LjAzOTEgMi4yODEyIDkuMzU5NCAzLjcxODggMTMuODAxIDMuMTIxMSA4LjY0MDYgNy4zMjAzIDE2LjA3OCAxMS43NjIgMjIuNjggOC44Nzg5IDEzLjA3OCAxOC42MDIgMjMuODc5IDI4LjU1OSAzMy40OCAxOS44MDEgMTkuNDQxIDQwLjMyIDM1LjY0MSA2MC44NCA1MS43MTkgNDEuMTYgMzEuNjggODIuNTU5IDYxLjU1OSAxMjMuNzIgOTEuOTIybDIzLjY0MSAxNy4yODFjLTUuMTYwMiAxNS42MDItMTAuNDQxIDMxLjMyLTE1LjYwMiA0Ny4wMzktMTYuMDc4IDQ4LjQ4LTMyLjY0MSA5Ni43MTktNDcuNjQxIDE0Ni44OC03LjMyMDMgMjUuMTk5LTE0LjUyIDUwLjc2Mi0xOS4wNzggNzkuMzItMS45MjE5IDE0LjUyLTMuNjAxNiAyOS43NjItMS41NTg2IDQ4IDEuMTk5MiA5LjEyMTEgMy4yMzgzIDE5LjA3OCA3LjkyMTkgMjkuMTZsMy43MTg4IDcuNTU4NmMxLjMyMDMgMi42NDA2IDIuMzk4NCAzLjk2MDkgMy42MDE2IDYgMi4zOTg0IDMuNzE4OCA1LjAzOTEgNy4zMjAzIDcuOTIxOSAxMC44MDEgMTEuMjgxIDEzLjkyMiAyNS40NDEgMjUuNTU5IDQxLjM5OCAzMy44NCA4LjAzOTEgNC4xOTkyIDE2LjQ0MSA3LjU1ODYgMjUuMDc4IDkuOTYwOSAxLjkyMTkgMC42MDE1NiA0LjY3OTcgMS4xOTkyIDcuNTU4NiAxLjY3OTdsOC41MTk1IDEuMzIwM2M1LjUxOTUgMC40ODA0NyAxMC42OCAwLjIzODI4IDE2LjA3OCAwLjIzODI4IDIwLjM5OC0xLjY3OTcgMzUuNTItNy44MDA4IDQ5LjQ0MS0xMy42OCAxNC4wMzktNiAyNi4xNi0xMi44NCAzOC4xNi0xOS42OCA0Ni45MjItMjcuODQgODguMDc4LTU3Ljk2MSAxMzAuMDgtODcuMzU5IDI0Ljk2MS0xNy42NDEgNTEuNjAyLTM2LjYwMiA3OC43MTktNTYuMDM5bDEzLjA3OCA5LjYwMTZjNDEuMjgxIDMwLjEyMSA4Mi4xOTkgNjAuNjAyIDEyNC44IDkwLjIzOCAyMS40OCAxNC43NjIgNDMuMDc4IDI5LjM5OCA2Ny4zMiA0Mi40OCAxMi4xMjEgNi40ODA1IDI1LjA3OCAxMi42MDIgMzkuOTYxIDE3LjI4MSAzLjk2MDkgMC45NjA5NCA3LjU1ODYgMi4xNjAyIDExLjc2MiAzIDQuMzIwMyAwLjYwMTU2IDguMzk4NCAxLjQ0MTQgMTIuODQgMS42Nzk3IDQuNjc5NyAwIDkuMTIxMSAwLjQ4MDQ3IDE0LjAzOS0wLjM1OTM4IDQuODAwOC0wLjcxODc1IDEwLjA3OC0xLjU1ODYgMTMuNjgtMi42NDA2IDE1LjcxOS00LjQ0MTQgMzAuNDgtMTIuMjM4IDQzLjA3OC0yMi42OCA2LjIzODMtNS4xNjAyIDEyLTExLjAzOSAxNy4xNi0xNy4zOThzOS4zNTk0LTEyLjcxOSAxMy42OC0yMi4xOTljNy41NTg2LTE3Ljg3OSA3LjY3OTctMzQuNDQxIDcuMDc4MS00OS4wNzgtMC44Mzk4NC0xNC43NjItMy0yOC41NTktNS42NDA2LTQxLjc2Mi0xMS4xNi01Mi42OC0yNy40OC0xMDEuMTYtNDIuNzE5LTE1MC4xMmwtMzUuMzk4LTExMC4yOGMyMS4xMjEtNi4yMzgzIDQ5LjgwMS0yMy4xNiA4MS44NC00NC43NjIgMjguNTU5LTE5LjE5OSA1OS42NDEtNDIuMzU5IDkwLTY3LjE5OSAxNS4xMjEtMTIuNDggMzAtMjUuNDQxIDQ0LjE2LTM5LjIzOCAxMy45MjItMTMuOTIyIDI3LjQ4LTI4LjY4IDM3LjU1OS00OC4xMjEgMS45MjE5LTMuODM5OCAzLjgzOTgtNy42Nzk3IDUuMTYwMi0xMi4yMzhsMi4xNjAyLTYuNjAxNiAxLjMyMDMtNy4xOTkyYzAuOTYwOTQtNS4xNjAyIDEuMDc4MS05LjEyMTEgMS4xOTkyLTEzLjE5OSAwLTQuMDc4MSAwLTguMTYwMi0wLjQ4MDQ3LTEyLjIzOC0xLjQ0MTQtMTYuMzItNi4xMjExLTMyLjM5OC0xMy44MDEtNDYuODAxLTMuODM5OC03LjE5OTItOC4zOTg0LTE0LjE2LTEzLjY4LTIwLjM5OC0zLjIzODMtMy40ODA1LTYuODM5OC03LjMyMDMtMTAuNDQxLTEwLjMyLTMuNzE4OC0yLjY0MDYtNy41NTg2LTUuODc4OS0xMS4zOTgtNy44MDA4LTE1LjQ4LTguODc4OS0zMC4yMzgtMTIuODQtNDQuMjgxLTE1LjcxOS0yOC4xOTktNS43NjE3LTU0LjM1OS02Ljk2MDktODAuNTItOC4yODEyLTI2LjE2LTEuMDc4MS01MS44NC0xLjQ0MTQtNzcuNTItMS41NTg2aC0xMjYuOTZsLTM1LjY0MS0xMTIuMDhjLTcuOTIxOS0yNC4zNTktMTUuODQtNDguODQtMjQuNDgtNzMuNDQxLTguNzYxNy0yNC42MDItMTcuNzYyLTQ5LjE5OS0zMC4xMjEtNzQuMTYtNi4yMzgzLTEyLjQ4LTEzLjE5OS0yNS4wNzgtMjMuNjQxLTM3LjgwMS01LjE2MDItNi4yMzgzLTExLjM5OC0xMi40OC0xOS4zMi0xOC0zLjYwMTYtMi44Nzg5LTguNTE5NS01LjAzOTEtMTIuODQtNy4zMjAzLTQuMTk5Mi0xLjkyMTktNy44MDA4LTMuMTIxMS0xMS44NzktNC40NDE0LTE1Ljg0LTUuMDM5MS0zMi43NjItNi42MDE2LTQ5LjE5OS00LjgwMDgtMTYuNTU5IDIuMjgxMi0zMi4wMzkgNS43NjE3LTQ5LjE5OSAxOC0xNS4xMjEgMTEuNTItMjQuMTIxIDI0LjcxOS0zMS45MjIgMzcuMDc4LTcuNTU4NiAxMi42MDItMTMuNDQxIDI0Ljk2MS0xOS4wNzggMzcuNDQxLTEwLjkyMiAyNC43MTktMTkuNjggNDkuMTk5LTI4LjMyIDczLjY4LTE4LjM1OSA1NS4xOTktMzYuNjAyIDExMC40LTU0Ljk2MSAxNjUuNDhoLTk1Ljg3OWMtNTEuMzU5IDAuNDgwNDctMTAyLjM2LTAuMjM4MjgtMTU2LjI0IDUuMjgxMi0xMy40NDEgMS4zMjAzLTI3LjM1OSAzLjcxODgtNDEuNzYyIDcuMzIwMy0xNC4yODEgMy44Mzk4LTMwLjEyMSA5LjIzODMtNDUuMjM4IDIxLjk2MS0zLjQ4MDUgMy4zNTk0LTcuNTU4NiA3LjMyMDMtMTAuMDc4IDEwLjQ0MS0yLjY0MDYgMy4yMzgzLTUuMDM5MSA2LjYwMTYtNy4zMjAzIDkuOTYwOS00LjU1ODYgNi45NjA5LTguMjgxMiAxNC4yODEtMTEuMjgxIDIxLjk2MS02IDE1LjM1OS05IDMxLjkyMi04LjUxOTUgNDguMzU5bDAuMzU5MzggNi4yMzgzIDEuMDc4MSA3LjMyMDN6bTcxNi42NC02NS42NDEgNjguNjQxIDIxMyAyNS4wNzggNzcuODc5Yy01NCAyMS42MDItMTQ4LjMyIDg3LjQ4LTIzOC42OCAxNTNsLTguMzk4NC02LjEyMTEtMjIyLjEyLTE2My42OCA4Ny44NC0yNzQuMzJoMTI3LjJsMTYwLjU2IDAuMzU5Mzd6bS0yNDUuMDQgNTE2Ljk2Yy00MC4zMiAyOS4yODEtODAuNTIgNTkuMTYtMTIwLjM2IDg1LjA3OC0xOS42OCAxMi43MTktNDAuMTk5IDI0Ljg0LTU2LjM5OCAzMC4zNTktNy45MjE5IDIuODc4OS0xMy42OCAzLTEzLjkyMiAyLjc2MTdoLTAuMjM4MjhjLTAuMjM4MjggMC0wLjcxODc1LTAuMjM4MjgtMS4wNzgxLTAuMjM4MjgtMC44Mzk4NC0wLjIzODI4LTEuNTU4Ni0wLjM1OTM4LTIuMjgxMi0wLjcxODc1LTEuNTU4Ni0wLjQ4MDQ3LTMuMTIxMS0xLjA3ODEtNC41NTg2LTEuODAwOC0zLTEuMzIwMy01Ljc2MTctMi44Nzg5LTguNTE5NS00LjgwMDgtNS4yODEyLTMuODM5OC05Ljk2MDktOC42NDA2LTEzLjMyLTE0LjI4MS0wLjQ4MDQ3LTAuNDgwNDctMi4wMzkxLTQuNjc5Ny0yLjAzOTEtMTIuOTYxIDAtMTYuODAxIDQuNTU4Ni0zOS44NCAxMC40NDEtNjIuNTIgMTEuODc5LTQ1Ljg0IDI3LjQ4LTkzLjQ4IDQyLjYwMi0xNDAuODhsMTYuNjgtNTIuMDc4IDE1Ny41NiAxMTUuMzIgMzYuNjAyIDI2Ljc2MmMtMTQuMDM5IDEwLjMyLTI3LjcxOSAyMC4yODEtNDAuOTIyIDI5Ljg3OXptNDI1LjI4IDgzLjM5OGMtMC4xMjEwOSAxLjkyMTktMC4yMzgyOCAzLjk2MDktMC4zNTkzOCA1Ljg3ODktMC4yMzgyOCAxLjU1ODYtMC42MDE1NiAyLjg3ODktMC43MTg3NSA0LjQ0MTQtMC40ODA0NyAwLjgzOTg0LTAuNjAxNTYgMS45MjE5LTAuODM5ODQgMi41MTk1LTAuMjM4MjggMC4xMjEwOS0wLjM1OTM4IDAuMzU5MzgtMC4zNTkzOCAwLjQ4MDQ3djAuMzU5MzhsLTAuNzE4NzUgMS4wNzgxYy0zLjk2MDkgNi05IDExLjE2LTE1IDE1LTMgMS45MjE5LTYuMTIxMSAzLjQ4MDUtOS4zNTk0IDQuODAwOC0xLjY3OTcgMC42MDE1Ni0zLjM1OTQgMS4xOTkyLTUuMDM5MSAxLjY3OTctMS4wNzgxIDAuMzU5MzgtMS4zMjAzIDAuMjM4MjgtMS40NDE0IDAuMjM4MjgtMC4xMjEwOSAwLTAuMzU5MzggMC0wLjQ4MDQ3IDAuMTIxMDktMi4wMzkxIDAuMzU5MzgtOS44Mzk4LTAuODM5ODQtMTguODQtNC44MDA4LTkuMTIxMS0zLjgzOTgtMTkuMDc4LTguNzYxNy0yOS4yODEtMTQuODc5LTQxLjAzOS0yNC4zNTktODMuMjgxLTU2LjE2LTEyNS4wNC04Ni42NDFsLTQzLjkyMi0zMi4zOThjNzQuNjQxLTU1LjE5OSAxNDUuMDgtMTExIDE4Mi40LTE1Mi41MmwzLjIzODMgMTAuMDc4YzE1LjIzOCA0Ny42NDEgMzAuODQgOTUuMTYgNDQuNTIgMTQyLjA4IDcuMDc4MSAyNC4zNTkgMTMuODAxIDQ4Ljg0IDE4IDcxLjY0MSAxLjkyMTkgMTEuMTYgMy4yMzgzIDIyLjA3OCAzLjIzODMgMzAuOTYxem01MC4wMzktNTk5LjI4YzI1LjMyIDAuNzE4NzUgNTAuNTIgMS44MDA4IDczLjMyIDQuNjc5NyAxMS4wMzkgMS41NTg2IDIxLjcxOSAzLjYwMTYgMjkuNjQxIDYuMjM4MyAxLjY3OTcgMC43MTg3NSAzLjU5NCAxLjQ0MTQgNS4wMzkxIDIuMDM5MSAxLjMyMDMgMC43MTg3NSAyLjI4MTIgMS4zMjAzIDMuNDgwNSAxLjgwMDggMC40ODA0NyAwLjYwMTU2IDEuMTk5MiAwLjk2MDk0IDEuNTU4NiAxLjE5OTIgMCAwLjEyMTA5IDAgMC4yMzgyOCAwLjEyMTA5IDAuMjM4MjhoMC4yMzgyOGwwLjcxODc1IDAuOTYwOTRjNC4xOTkyIDUuMjgxMiA3LjMyMDMgMTEuMzk4IDkgMTcuODc5IDAuODM5ODQgMy4yMzgzIDEuMzIwMyA2LjYwMTYgMS41NTg2IDkuOTYwOXY1LjAzOTEgMS4zMjAzcy0wLjIzODI4IDAuMTIxMDktMC4yMzgyOCAwLjIzODI4djAuMzU5MzhjLTAuMTIxMDkgMi4wMzkxLTYuNDgwNSAxMi45NjEtMTcuMjgxIDIzLjY0MS0xMC42OCAxMC45MjItMjQuNDggMjIuNDQxLTM4Ljc2MiAzMy44NC0yOC41NTkgMjIuODAxLTU5Ljc2MiA0NS40OC04Ni41MiA2Ny4wNzgtMjYuODc5IDIxLjIzOC00OS40NDEgNDEuNjQxLTY0LjE5OSA1OS4zOThsLTc1LjcxOS0yMzYuODhoODAuNzYyYzI2LjAzOSAwLjIzODI4IDUxLjk2MSAwLjM1OTM4IDc3LjI4MSAxLjA3ODF6bS00NjIuMzYtMTc1LjA4YzcuNjc5Ny0yMy41MiAxNS4zNTktNDcuMDM5IDIzLjY0MS02OS42MDIgOC4xNjAyLTIyLjQ0MSAxNi45MjItNDQuODc5IDI2LjY0MS02My4xMjEgNC44MDA4LTkgMTAuMDc4LTE2LjU1OSAxNC4wMzktMjAuNjQxIDAuOTYwOTQtMS4wNzgxIDEuOTIxOS0yLjAzOTEgMi41MTk1LTIuMjgxMiAwLjM1OTM4LTAuMjM4MjggMC42MDE1Ni0wLjQ4MDQ3IDAuODM5ODQtMC44Mzk4NGgwLjQ4MDQ3YzAuMzU5MzggMC0wLjIzODI4LTAuMjM4MjggMC43MTg3NS0wLjQ4MDQ3IDAuODM5ODQtMC4yMzgyOCAxLjU1ODYtMC42MDE1NiAyLjM5ODQtMC44Mzk4NCAxLjU1ODYtMC42MDE1NiAzLjEyMTEtMS4wNzgxIDQuODAwOC0xLjQ0MTQgNi40ODA1LTEuNTU4NiAxMy4zMi0xLjgwMDggMTkuODAxLTAuNjAxNTYgMy4yMzgzIDAuNjAxNTYgNi40ODA1IDEuNDQxNCA5LjYwMTYgMi42NDA2IDEuNDQxNCAwLjYwMTU2IDAuNzE4NzUgMC43MTg3NSAxLjQ0MTQgMC43MTg3NSAwLjQ4MDQ3IDAuNDgwNDcgMS4xOTkyIDEuMDc4MSAxLjkyMTkgMS40NDE0IDMuNDgwNSAyLjc2MTcgOC44Nzg5IDEwLjE5OSAxMy44MDEgMTguNzE5IDUuMDM5MSA4LjM5ODQgOS43MTg4IDE4Ljg0IDE0LjI4MSAyOS4wMzkgOSAyMS4yMzggMTcuMjgxIDQ0LjAzOSAyNS4xOTkgNjcuMTk5IDE1Ljg0IDQ2LjE5OSAzMC44NCA5My43MTkgNDYuMTk5IDE0MWgtMTA3LjQtMTMzLjMybDMyLjI4MS0xMDAuNjh6bS00MTEuMTIgMjA1LjhjMS4xOTkyLTMuMjM4MyAyLjY0MDYtNi4zNTk0IDQuNDQxNC05LjM1OTQgMC45NjA5NC0xLjQ0MTQgMS45MjE5LTIuODc4OSAyLjg3ODktNC4xOTkyIDAuNDgwNDctMC42MDE1NiAxLjE5OTItMS41NTg2IDEuNDQxNC0xLjgwMDggMC4yMzgyOCAwIDAuMjM4MjggMCAwLjM1OTM4LTAuMjM4MjggMC42MDE1Ni0wLjk2MDk0IDYuODM5OC00LjU1ODYgMTUuOTYxLTYuODM5OCAxOC4yMzgtNC45MjE5IDQzLjMyLTYuOTYwOSA2Ny45MjItOC4yODEyIDI0Ljk2MS0xLjE5OTIgNTAuNjQxLTEuNDQxNCA3Ni40NDEtMS42Nzk3aDEwNy43NmMtMjQuOTYxIDc1LjQ4LTUwLjAzOSAxNTAuODQtNzUgMjI2LjJsLTkwLjQ4LTY2Ljk2MWMtMjAuNjQxLTE1LjQ4LTQxLjAzOS0zMS4wNzgtNjAuMTIxLTQ2LjkyMi0xOC44NC0xNS42MDItMzcuNDQxLTMyLjM5OC00OC00Ni44MDEtNS4xNjAyLTcuMTk5Mi02LjcxODgtMTIuMTIxLTYuNjAxNi0xMi43MTktMC40ODA0Ny02Ljk2MDkgMC42MDE1Ni0xNC4wMzkgMi44Nzg5LTIwLjUyeiIvPgo8L3N2Zz4K" alt="Built with Spellbook"></a>
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
| [/compact] | Custom session compaction | spellbook |
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

[/compact]: https://axiomantic.github.io/spellbook/latest/commands/compact/
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

Without autonomous mode, you'll be prompted to approve each file write, command execution, etc. The workflows still function, but require manual approval at each step.

See platform documentation for details: [Claude Code](https://docs.anthropic.com/en/docs/claude-code), [OpenCode](https://opencode.ai/docs/permissions/), [Codex](https://developers.openai.com/codex/cli/reference/), [Gemini CLI](https://github.com/google-gemini/gemini-cli).

## Workflow Recipes

### End-to-End Feature Implementation

The `implement-feature` skill orchestrates the complete workflow from requirements to PR.

```
You: "Implement user authentication with MFA support"

# implement-feature triggers automatically and runs:
#   → brainstorming (explores requirements, gathers context)
#   → design-doc-reviewer (validates architecture)
#   → writing-plans (creates detailed implementation plan)
#   → implementation-plan-reviewer (verifies plan completeness)
#   → test-driven-development (per task, in parallel worktrees)
#   → code-reviewer (after each change)
#   → finishing-a-development-branch (creates PR)
```

Configuration options prompt at start: autonomous mode, parallel worktrees, auto-PR.

### Work Packets for Large Features

For large features where even heavy subagent use would exhaust the orchestrator's context, `implement-feature` splits work into **work packets** that run in completely separate sessions.

```
You: "Implement user authentication with MFA support"

# implement-feature analyzes the work:
#   Token estimation: 150,000 tokens (~75% of context)
#   Tasks: 24 across 4 tracks
#   Recommendation: "swarmed" mode

# You choose execution mode, then work packets are generated:
~/.claude/work-packets/user-auth/
├── manifest.json           # Track metadata, dependencies
├── track-1-backend.md      # Boot prompt for backend work
├── track-2-frontend.md     # Boot prompt for frontend work
├── track-3-tests.md        # Boot prompt for test work
└── track-4-docs.md         # Boot prompt for docs
```

Execute packets in parallel terminals:
```
/execute-work-packet ~/.claude/work-packets/user-auth/track-1-backend.md
```

When all tracks complete:
```
/merge-work-packets ~/.claude/work-packets/user-auth/
```

**Execution modes:**

| Mode | When | What happens |
|------|------|--------------|
| `swarmed` | 25+ tasks or 80%+ context | Parallel sessions, one per track |
| `sequential` | 16-25 tasks or 65-80% | Single session, processes packets in order |
| `delegated` | 9-15 tasks or 40-65% | Current session, heavy subagent use |
| `direct` | ≤8 tasks and <40% | Current session, minimal delegation |

### Session Handoff Between Assistants

Pause work in one assistant, resume in another with full context.

```
# In Cursor/Windsurf/any assistant, when you need to switch:
/distill-session

# Output: Session saved to ~/.claude/distilled/<project>/session-20260105-143022.md

# In your new session (after /clear or in a different assistant):
You: "Continue work from ~/.claude/distilled/<project>/session-20260105-143022.md"
```

The distilled file contains decisions, plans, and progress. 50K tokens compress to ~3K words.

### Using Skills

Skills trigger automatically based on what you ask for. You don't invoke them explicitly.

```
You: "I want to add dark mode support"
# implement-feature triggers, orchestrates the full workflow

You: "Tests are failing and I don't know why"
# debug skill triggers, guides systematic investigation

You: "Let's think through the architecture before coding"
# brainstorming skill triggers, explores requirements first
```

See [Platform Support](#platform-support) for which assistants have native skill support. To add support for a new assistant, see the [Porting Guide](docs/contributing/porting-to-your-assistant.md).

### Parallel Worktree Development

Work on multiple parts of a feature simultaneously in isolated branches.

```
You: "Let's design the new payment system"
# brainstorming skill kicks in, creates design with interface contracts

You: "Set up worktrees for this"
# using-git-worktrees creates: .worktrees/payment-api, .worktrees/payment-ui, .worktrees/payment-tests

You: "Work on these in parallel"
# Spawns subagents, each working in their own worktree

You: "Merge the worktrees"
# smart-merge synthesizes changes using 3-way diff analysis
```

### Audit Test Quality

Check whether tests actually catch bugs, not just achieve coverage.

```
/green-mirage-audit

# Output: ~/.claude/docs/<project>/audits/green-mirage-audit-20260105-143022.md
# Shows which tests are SOLID vs GREEN MIRAGE (false confidence)

You: "Fix the issues from the audit"
# fix-tests skill takes the report and rewrites weak tests
```

### Find Past Patterns

The MCP server provides tools to query old sessions.

```
You: "Find sessions where I worked on async retry logic"
# Uses find_session MCP tool, returns matching sessions with metadata

You: "Load that session and show me the retry pattern I used"
# Uses split_session to load chunks, extracts the relevant code
```

### Create Custom Skills

Encode team-specific workflows as shareable markdown files.

```
You: "Help me create a skill for our GraphQL schema testing workflow"
# writing-skills guides you through:
#   - Skill name and description
#   - When it should trigger
#   - Step-by-step workflow
#   - Quality gates and outputs

# Result: ~/.claude/skills/graphql-schema-testing.md
# Share via Git - your team gets the same workflow
```

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
