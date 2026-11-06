# ROCKSOUL — Product Narrative

> **One runtime. A better way to work with AI.**

## The idea

g4f already brings together Python interfaces, providers, models, tools, and inference APIs. ROCKSOUL gives that capability a distinctive, coherent product experience.

ROCKSOUL is the new face of g4f: a thoughtfully designed interface that replaces the default HTML experience while respecting the Python runtime that powers it.

## Mission

Make powerful, diverse AI capabilities approachable through one fast, expressive, reliable interface—without hiding limitations or duplicating the machinery underneath.

## Vision

A unified AI workspace that feels modern and intentional across chat, models, providers, tools, media, settings, and conversation history. It should be easy for a first-time user and efficient for a developer who already knows g4f.

## What ROCKSOUL is

- The primary web UI and visual identity for g4f.
- A chat-first workspace over existing g4f APIs.
- A responsive experience for existing provider and model capabilities.
- A coherent home for settings, history, diagnostics and supported tools.
- A presentation layer that makes runtime capabilities understandable.

## What ROCKSOUL is not

- A second Python runtime.
- A new LLM gateway or provider aggregator.
- A parallel provider registry, model catalog, router or fallback engine.
- A replacement for g4f's API, Python SDK or provider implementations.
- An autonomous-agent platform or an AGI claim.
- A requirement to enable WorkItem, WorkGraph, Arena or Mesh for ordinary chat.

## Product principles

1. **Runtime first:** g4f remains the source of truth for models, providers, execution and API behavior.
2. **UI owns presentation:** ROCKSOUL owns interaction, navigation, visual hierarchy and accessibility—not inference.
3. **Compatibility over reinvention:** preserve g4f routes, payloads, sessions and SDKs.
4. **Honest capability display:** show only what the runtime actually supports.
5. **Fast and direct:** streaming should feel immediate; avoid needless proxying and buffering.
6. **Progressive complexity:** simple chat first; advanced controls appear when relevant.
7. **Recoverability:** keep a fallback to the existing UI until replacement parity is proven.
8. **Privacy by design:** never expose provider secrets or server credentials to the browser.

## The experience

ROCKSOUL should feel like a focused AI workspace, not an infrastructure dashboard. The primary screen is conversation-first. Model/provider selection, attachments, tools, and generation options are accessible without overwhelming the chat. History and workspace navigation remain predictable. Diagnostics are available but do not dominate the product.

The visual language may be bold, experimental and distinctive, but readability, speed, keyboard access, responsive behavior and user control remain non-negotiable.

## Product promise

**One proven runtime. One coherent interface.**

We will not create a second gateway just to give the product a new face. We will preserve the working Python engine and make the experience around it substantially better.

## Optional engineering modules

Arena, Mesh, WorkItem, WorkGraph, evidence verification and operator tooling may remain as optional experiments or developer utilities. They do not define the ROCKSOUL product and must not become dependencies of the normal chat experience.

## The commitment

Ship the interface users can actually use. Preserve the runtime that already works. Label unfinished parity honestly. Remove legacy HTML only after the replacement is tested—not before.
