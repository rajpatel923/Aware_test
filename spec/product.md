# Messaging Client Specification

## Purpose

implement a minimal direct messaging client.

## Requirements

A user must:
1. users should identify themselves by a unique name on first launch.
2. send a text message to another users via username
3. receive messages from the server
4. queue outgoing messages first onto a queue before sending them.
5. save messages on queue when offline
6. automatically send queued messages when online.

## Platforms

Two independent client implementations are required.

- IOS - Swift
- Android - Kotlin

The implementation must not share client source code.

## OUT OF SCOPE

- authentication
- encryption
- group messaging
- attachments
- cloud infra
- message editing
- message deletion