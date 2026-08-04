package com.financialrag.backend.web;

import java.time.Instant;
import java.util.List;

import jakarta.servlet.http.HttpServletRequest;

import org.springframework.http.HttpStatus;

public record ApiError(
        Instant timestamp,
        int status,
        String error,
        String message,
        String requestId,
        String path,
        List<FieldError> fieldErrors) {

    public static ApiError of(
            HttpStatus status,
            String error,
            String message,
            HttpServletRequest request) {
        return of(status, error, message, request, List.of());
    }

    public static ApiError of(
            HttpStatus status,
            String error,
            String message,
            HttpServletRequest request,
            List<FieldError> fieldErrors) {
        return new ApiError(
                Instant.now(),
                status.value(),
                error,
                message,
                RequestIdFilter.getRequestId(request),
                request.getRequestURI(),
                List.copyOf(fieldErrors));
    }

    public record FieldError(String field, String message) {
    }
}
