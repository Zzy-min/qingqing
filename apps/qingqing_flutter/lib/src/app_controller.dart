import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'api_client.dart';

class AppController extends ChangeNotifier {
  AppController({ApiClient? api, FlutterSecureStorage? storage})
    : api = api ?? ApiClient(),
      _storage = storage ?? const FlutterSecureStorage();
  final ApiClient api;
  final FlutterSecureStorage _storage;
  static const _tokenKey = 'qingqing_session_token';
  bool authenticated = false;
  bool busy = false;
  bool advancedMode = false;
  String credentialPreference = 'platform_first';
  String? devCode;
  String? error;

  List<dynamic> activeRuns = [];
  List<dynamic> artifacts = [];
  Map<String, dynamic>? entitlements;
  final Set<String> _pollingRunIds = {};

  Future<void> restoreSession() async {
    if (kIsWeb) return;
    final token = await _storage.read(key: _tokenKey);
    if (token == null || token.isEmpty) return;
    api.token = token;
    try {
      await api.request('/api/v1/me/entitlements');
      authenticated = true;
      await Future.wait([
        loadEntitlements(),
        loadPreferences(),
        loadRuns(),
        loadArtifacts(),
      ]);
    } on ApiException {
      await _storage.delete(key: _tokenKey);
      api.token = null;
    }
  }

  Future<void> requestCode(String email) async {
    await _guard(() async {
      final data = await api.request(
        '/api/v1/auth/email/request-code',
        method: 'POST',
        body: {'email': email},
      );
      devCode = data['dev_code']?.toString();
    });
  }

  Future<void> verifyCode(String email, String code) async {
    await _guard(() async {
      final data = await api.request(
        '/api/v1/auth/email/verify',
        method: 'POST',
        body: {'email': email, 'code': code},
      );
      api.token = data['access_token']?.toString();
      authenticated = api.token != null;
      final token = api.token;
      if (!kIsWeb && token != null) {
        await _storage.write(key: _tokenKey, value: token);
      }
      await Future.wait([
        loadEntitlements(),
        loadPreferences(),
        loadRuns(),
        loadArtifacts(),
      ]);
    });
  }

  Future<void> loadEntitlements() async {
    try {
      final data = await api.request('/api/v1/me/entitlements');
      entitlements = data;
      notifyListeners();
    } on ApiException catch (exception) {
      if (exception.statusCode == 401) await logout();
      error = exception.message;
      notifyListeners();
    }
  }

  Future<void> loadPreferences() async {
    try {
      final data = await api.request('/api/v1/me/preferences');
      advancedMode = data['advanced_mode_enabled'] == true;
      credentialPreference =
          data['credential_preference']?.toString() ?? 'platform_first';
      notifyListeners();
    } on ApiException catch (exception) {
      if (exception.statusCode == 401) await logout();
      error = exception.message;
      notifyListeners();
    }
  }

  Future<void> loadArtifacts() async {
    try {
      final data = await api.request('/api/v1/artifacts');
      artifacts = data['artifacts'] as List<dynamic>? ?? [];
      notifyListeners();
    } on ApiException catch (exception) {
      if (exception.statusCode == 401) await logout();
      error = exception.message;
      notifyListeners();
    }
  }

  Future<void> loadRuns() async {
    try {
      final data = await api.request('/api/v1/agent/runs');
      activeRuns = List<dynamic>.from(
        data['runs'] as List<dynamic>? ?? const [],
      );
      notifyListeners();
      for (final run in activeRuns) {
        if (run['status'] == 'running') {
          unawaited(_pollRun(run['id'].toString()));
        }
      }
    } on ApiException catch (exception) {
      if (exception.statusCode == 401) await logout();
      error = exception.message;
      notifyListeners();
    }
  }

  Future<Map<String, dynamic>?> submitAgentRun(
    String goal,
    Map<String, dynamic> routing,
  ) async {
    return await _guard(() async {
      final data = await api.request(
        '/api/v1/agent/runs',
        method: 'POST',
        headers: {
          'Idempotency-Key': DateTime.now().microsecondsSinceEpoch.toString(),
        },
        body: {'goal': goal, 'routing': routing},
      );
      var current = data;
      if (data['status'] == 'planned') {
        current = await api.request(
          '/api/v1/agent/runs/${data['id']}/execute',
          method: 'POST',
        );
      }
      final newRun = Map<String, dynamic>.from(current);
      activeRuns = [
        newRun,
        ...activeRuns.where((item) => item['id'] != newRun['id']),
      ];
      if (newRun['status'] == 'running') {
        unawaited(_pollRun(newRun['id'].toString()));
      }
      await loadEntitlements();
      await loadArtifacts();
      return newRun;
    });
  }

  Future<void> executeRun(String runId) async {
    await _guard(() async {
      await api.request('/api/v1/agent/runs/$runId/execute', method: 'POST');
      final idx = activeRuns.indexWhere((r) => r['id'] == runId);
      if (idx != -1) {
        activeRuns = [
          for (var i = 0; i < activeRuns.length; i++)
            if (i == idx)
              {...activeRuns[i], 'status': 'running'}
            else
              activeRuns[i],
        ];
      }
      unawaited(_pollRun(runId));
      await loadArtifacts();
    });
  }

  Future<void> approveRun(String runId) async {
    await _guard(() async {
      await api.request('/api/v1/agent/runs/$runId/approve', method: 'POST');
      final data = await api.request(
        '/api/v1/agent/runs/$runId/execute',
        method: 'POST',
      );
      final idx = activeRuns.indexWhere((r) => r['id'] == runId);
      if (idx != -1) {
        activeRuns = [
          for (var i = 0; i < activeRuns.length; i++)
            if (i == idx) data else activeRuns[i],
        ];
      }
      unawaited(_pollRun(runId));
      await loadEntitlements();
    });
  }

  Future<void> cancelRun(String runId) async {
    await _guard(() async {
      final data = await api.request(
        '/api/v1/agent/runs/$runId/cancel',
        method: 'POST',
      );
      final idx = activeRuns.indexWhere((r) => r['id'] == runId);
      if (idx != -1) {
        activeRuns = [
          for (var i = 0; i < activeRuns.length; i++)
            if (i == idx) data else activeRuns[i],
        ];
      }
      await loadEntitlements();
    });
  }

  Future<void> savePreferences({bool? advanced, String? credential}) async {
    await _guard(() async {
      final body = <String, Object>{};
      if (advanced != null) {
        body['advanced_mode_enabled'] = advanced;
      }
      if (credential != null) {
        body['credential_preference'] = credential;
      }
      final data = await api.request(
        '/api/v1/me/preferences',
        method: 'PATCH',
        body: body,
      );
      advancedMode = data['advanced_mode_enabled'] == true;
      credentialPreference =
          data['credential_preference']?.toString() ?? credentialPreference;
      await loadEntitlements();
    });
  }

  Future<void> logout() async {
    if (!kIsWeb) await _storage.delete(key: _tokenKey);
    api.token = null;
    authenticated = false;
    advancedMode = false;
    credentialPreference = 'platform_first';
    activeRuns = [];
    artifacts = [];
    entitlements = null;
    _pollingRunIds.clear();
    notifyListeners();
  }

  Future<void> _pollRun(String runId) async {
    if ((!authenticated && api.token == null) || !_pollingRunIds.add(runId)) {
      return;
    }
    try {
      for (var attempt = 0; attempt < 30; attempt++) {
        if (!authenticated && api.token == null) return;
        await Future<void>.delayed(
          Duration(
            milliseconds: attempt < 2 ? 500 : (attempt < 8 ? 1500 : 4000),
          ),
        );
        final data = await api.request('/api/v1/agent/runs/$runId');
        final updated = Map<String, dynamic>.from(data);
        activeRuns = [
          updated,
          ...activeRuns.where((item) => item['id'] != runId),
        ];
        notifyListeners();
        final status = updated['status']?.toString();
        if ({'completed', 'failed', 'cancelled', 'paused'}.contains(status)) {
          await Future.wait([loadArtifacts(), loadEntitlements()]);
          return;
        }
      }
    } on ApiException catch (exception) {
      if (exception.statusCode == 401) await logout();
    } finally {
      _pollingRunIds.remove(runId);
    }
  }

  Future<T?> _guard<T>(Future<T> Function() action) async {
    busy = true;
    error = null;
    notifyListeners();
    try {
      return await action();
    } on ApiException catch (exception) {
      error = exception.message;
      return null;
    } finally {
      busy = false;
      notifyListeners();
    }
  }
}
