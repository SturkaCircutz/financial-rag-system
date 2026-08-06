package com.financialrag.backend.rag;

import com.financialrag.backend.web.RequestIdFilter;
import org.slf4j.MDC;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;
import org.springframework.http.client.ClientHttpRequestInterceptor;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

@Component
@ConditionalOnProperty(prefix = "rag.service", name = "mode", havingValue = "http")
public class HttpRagClient implements RagClient {

    private final RestClient restClient;

    @Autowired
    public HttpRagClient(RagServiceProperties properties, RestClient.Builder restClientBuilder) {
        this(buildRestClient(properties, restClientBuilder));
    }

    HttpRagClient(RestClient restClient) {
        this.restClient = restClient;
    }

    @Override
    public RagServiceContract.GenerateReportResponse generateReport(
            RagServiceContract.GenerateReportRequest request) {
        RagServiceContract.GenerateReportResponse response = restClient.post()
                .uri("/v1/reports:generate")
                .contentType(MediaType.APPLICATION_JSON)
                .body(request)
                .retrieve()
                .body(RagServiceContract.GenerateReportResponse.class);

        if (response == null) {
            throw new IllegalStateException("RAG service returned an empty response body.");
        }
        return response;
    }

    private static RestClient buildRestClient(
            RagServiceProperties properties,
            RestClient.Builder restClientBuilder) {
        SimpleClientHttpRequestFactory requestFactory = new SimpleClientHttpRequestFactory();
        requestFactory.setConnectTimeout(properties.getTimeout());
        requestFactory.setReadTimeout(properties.getTimeout());

        return restClientBuilder
                .baseUrl(properties.getBaseUrl().toString())
                .requestFactory(requestFactory)
                .requestInterceptor(requestIdForwardingInterceptor())
                .build();
    }

    static ClientHttpRequestInterceptor requestIdForwardingInterceptor() {
        return (request, body, execution) -> {
            String requestId = MDC.get("requestId");
            if (requestId != null && !requestId.isBlank()) {
                request.getHeaders().set(RequestIdFilter.REQUEST_ID_HEADER, requestId);
            }
            return execution.execute(request, body);
        };
    }
}
