# Spec Roadmap

> Auto-updated index. Last updated: 2026-05-28（含 stats heatmap refinement + combo/macro UX 同步）
>
> **AI Agents**: Read this file first to decide which specs to load. Load only what's relevant to your task to avoid context bloat.

## Module Index

| Module | Spec | Domain Layer | Description | Sub-modules |
|--------|------|--------------|-------------|-------------|
| `keyboard-manager` | [keyboard-manager.spec.md](./keyboard-manager.spec.md) | Supporting Subdomain | macOS-only personal tool that parses Vial `.vil` for full keycode visualization and ingests global keystrokes via a host-side native helper for heatmap & live simulator. | — |

## Loading Guide

| Task Type | Load These Specs |
|-----------|-----------------|
| 實作 `.vil` parser / Static Viewer (M1) | `keyboard-manager.spec.md` + `../srs/keyboard-manager-mvp.srs.md` |
| 實作 SQLite + stats baseline (M2) | 同上，重點看 §Data Model + §API Contracts |
| 實作 Heatmap (M3) | 同上，重點看 §Architecture > Components > HeatmapMapper |
| 實作 Native helper + Interactive (M4) | 同上，重點看 §Architecture > Sequence Diagrams |
| 系統第一次理解 | 先讀本 SPEC_ROADMAP → `keyboard-manager.spec.md` → `../PRD.md` |

## Recent Feature Changes

| Date | Module | Feature SRS | One-line Summary |
|------|--------|-------------|-----------------|
| 2026-05-28 | `keyboard-manager` | [keyboard-manager-mvp.srs.md](../srs/keyboard-manager-mvp.srs.md) | MVP foundational delivery — `.vil` parser, SQLite stats, heatmap, native helper, live simulator |
| 2026-05-28 | `keyboard-manager` | — (spec inline change) | Heatmap refined to shortcut surface — typing keys filtered, modifier derivation, combo position index for firmware-level shortcuts |
| 2026-05-28 | `keyboard-manager` | — (spec inline change) | Combo / macro visual layer — corner-dot trigger badge, `expanded_kind="macro"` resolver path, Interactive combo legend with synchronized highlight, helper VK pairing to fix combo chip residue |
