import 'dart:convert';

import 'package:http/http.dart' as http;

class ApiException implements Exception {
  const ApiException(this.message, this.statusCode);
  final String message;
  final int statusCode;
}

class ApiClient {
  ApiClient({http.Client? client}) : _client = client ?? http.Client();
  final http.Client _client;
  static const _base = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://localhost:8001',
  );
  String? token;

  Future<Map<String, dynamic>> request(
    String path, {
    String method = 'GET',
    Object? body,
    Map<String, String>? headers,
  }) async {
    final requestHeaders = <String, String>{
      'Content-Type': 'application/json',
      ...?headers,
    };
    if (token case final value?) {
      requestHeaders['Authorization'] = 'Bearer $value';
    }
    final uri = Uri.parse('$_base$path');
    final encoded = body == null ? null : jsonEncode(body);
    final response = switch (method) {
      'POST' => await _client.post(uri, headers: requestHeaders, body: encoded),
      'PATCH' => await _client.patch(
        uri,
        headers: requestHeaders,
        body: encoded,
      ),
      'DELETE' => await _client.delete(uri, headers: requestHeaders),
      _ => await _client.get(uri, headers: requestHeaders),
    };
    final dynamic decoded = response.body.isEmpty
        ? <String, dynamic>{}
        : jsonDecode(response.body);
    if (response.statusCode < 200 || response.statusCode >= 300) {
      final message = decoded is Map<String, dynamic>
          ? decoded['detail']?.toString()
          : null;
      throw ApiException(message ?? '请求失败，请稍后重试', response.statusCode);
    }
    return decoded is Map<String, dynamic>
        ? decoded
        : <String, dynamic>{'data': decoded};
  }
}
