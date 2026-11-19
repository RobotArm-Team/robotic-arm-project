package com.robotarm.management.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.robotarm.management.api.ApiException;
import java.io.IOException;
import java.net.ConnectException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.net.http.HttpTimeoutException;
import java.time.Duration;
import java.util.Map;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

/**
 * 机械臂动作代理（板子上的 robot_agent.py）的 HTTP 客户端。
 *
 * <p>后端不直接操作串口：动作由板子上的代理执行，本类只做转发与错误码映射。
 */
@Service
public class RobotAgentClient {

    private static final TypeReference<Map<String, Object>> MAP_TYPE = new TypeReference<>() {
    };
    private static final ObjectMapper MAPPER = new ObjectMapper();

    private final HttpClient httpClient;
    private final String baseUrl;
    private final Duration requestTimeout;

    public RobotAgentClient(
            @Value("${robot.agent.base-url}") String baseUrl,
            @Value("${robot.agent.connect-timeout-ms:2000}") long connectTimeoutMs,
            @Value("${robot.agent.request-timeout-ms:5000}") long requestTimeoutMs) {
        this.baseUrl = baseUrl.endsWith("/") ? baseUrl.substring(0, baseUrl.length() - 1) : baseUrl;
        this.httpClient = HttpClient.newBuilder()
                .connectTimeout(Duration.ofMillis(connectTimeoutMs))
                .build();
        this.requestTimeout = Duration.ofMillis(requestTimeoutMs);
    }

    public Map<String, Object> health() {
        return send("GET", "/health");
    }

    public Map<String, Object> actions() {
        return send("GET", "/actions");
    }

    public Map<String, Object> state() {
        return send("GET", "/state");
    }

    public Map<String, Object> run(String action) {
        return send("POST", "/actions/" + action);
    }

    public Map<String, Object> stop() {
        return send("POST", "/stop");
    }

    // ---------- 手势识别（摄像头画面 + 手势类别） ----------

    public Map<String, Object> gestureStatus() {
        return send("GET", "/gesture/status");
    }

    public Map<String, Object> gestureLatest() {
        return send("GET", "/gesture/latest");
    }

    /** 开启识别；板子已在识别时返回已运行状态，不视为错误。 */
    public Map<String, Object> gestureStart() {
        HttpRequest request = HttpRequest.newBuilder(URI.create(baseUrl + "/gesture/start"))
                .timeout(requestTimeout)
                .header("Accept", "application/json")
                .method("POST", HttpRequest.BodyPublishers.noBody())
                .build();
        try {
            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() == 409) {
                return Map.of("status", "ALREADY_RUNNING");
            }
            return parse(response, "/gesture/start");
        } catch (ApiException exception) {
            throw exception;
        } catch (ConnectException | HttpTimeoutException exception) {
            throw unavailable(exception);
        } catch (IOException exception) {
            throw unavailable(exception);
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            throw new ApiException(HttpStatus.SERVICE_UNAVAILABLE, "SERVICE_UNAVAILABLE",
                    "机械臂代理请求被中断", null);
        }
    }

    public Map<String, Object> gestureStop() {
        return send("POST", "/gesture/stop");
    }

    /** 最新一帧 JPEG；还没有画面时返回 null。 */
    public byte[] gestureFrame() {
        HttpRequest request = HttpRequest.newBuilder(URI.create(baseUrl + "/gesture/frame"))
                .timeout(requestTimeout)
                .method("GET", HttpRequest.BodyPublishers.noBody())
                .build();
        try {
            HttpResponse<byte[]> response = httpClient.send(request, HttpResponse.BodyHandlers.ofByteArray());
            if (response.statusCode() == 200) {
                return response.body();
            }
            if (response.statusCode() == 404) {
                return null;
            }
            throw new ApiException(HttpStatus.BAD_GATEWAY, "ROBOT_AGENT_ERROR",
                    "机械臂代理返回状态 " + response.statusCode(), null);
        } catch (ApiException exception) {
            throw exception;
        } catch (ConnectException | HttpTimeoutException exception) {
            throw unavailable(exception);
        } catch (IOException exception) {
            throw unavailable(exception);
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            throw new ApiException(HttpStatus.SERVICE_UNAVAILABLE, "SERVICE_UNAVAILABLE",
                    "机械臂代理请求被中断", null);
        }
    }

    private Map<String, Object> parse(HttpResponse<String> response, String path) throws IOException {
        Map<String, Object> body = response.body() == null || response.body().isBlank()
                ? Map.of()
                : MAPPER.readValue(response.body(), MAP_TYPE);
        int status = response.statusCode();
        if (status >= 200 && status < 300) {
            return body;
        }
        if (status == 404) {
            throw new ApiException(HttpStatus.NOT_FOUND, "ACTION_NOT_FOUND",
                    "未知的机械臂动作：" + path.substring(path.lastIndexOf('/') + 1), null);
        }
        throw new ApiException(HttpStatus.BAD_GATEWAY, "ROBOT_AGENT_ERROR",
                "机械臂代理返回状态 " + status, null);
    }

    private ApiException unavailable(Exception exception) {
        return new ApiException(HttpStatus.SERVICE_UNAVAILABLE, "SERVICE_UNAVAILABLE",
                "无法连接机械臂代理（" + baseUrl + "）：" + exception.getMessage(), null);
    }

    private Map<String, Object> send(String method, String path) {
        HttpRequest request = HttpRequest.newBuilder(URI.create(baseUrl + path))
                .timeout(requestTimeout)
                .header("Accept", "application/json")
                .method(method, HttpRequest.BodyPublishers.noBody())
                .build();
        try {
            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
            Map<String, Object> body = response.body() == null || response.body().isBlank()
                    ? Map.of()
                    : MAPPER.readValue(response.body(), MAP_TYPE);
            int status = response.statusCode();
            if (status >= 200 && status < 300) {
                return body;
            }
            if (status == 409) {
                throw new ApiException(HttpStatus.CONFLICT, "ROBOT_BUSY",
                        "机械臂正在执行动作：" + body.get("action"), null);
            }
            if (status == 404) {
                String name = path.substring(path.lastIndexOf('/') + 1);
                throw new ApiException(HttpStatus.NOT_FOUND, "ACTION_NOT_FOUND",
                        "未知的机械臂动作：" + name, null);
            }
            throw new ApiException(HttpStatus.BAD_GATEWAY, "ROBOT_AGENT_ERROR",
                    "机械臂代理返回状态 " + status, null);
        } catch (ApiException exception) {
            throw exception;
        } catch (ConnectException | HttpTimeoutException exception) {
            throw new ApiException(HttpStatus.SERVICE_UNAVAILABLE, "SERVICE_UNAVAILABLE",
                    "无法连接机械臂代理（" + baseUrl + "）：" + exception.getMessage(), null);
        } catch (IOException exception) {
            throw new ApiException(HttpStatus.SERVICE_UNAVAILABLE, "SERVICE_UNAVAILABLE",
                    "机械臂代理请求失败：" + exception.getMessage(), null);
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            throw new ApiException(HttpStatus.SERVICE_UNAVAILABLE, "SERVICE_UNAVAILABLE",
                    "机械臂代理请求被中断", null);
        }
    }
}
