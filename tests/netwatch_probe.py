"""Positive control for netwatch: a numeric address lookup (no traffic) that must be recorded as not loopback."""
import socket

socket.getaddrinfo("192.0.2.1", 80)      # TEST-NET-1, resolved locally without any packet
