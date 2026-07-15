import 'package:flutter/material.dart';

import '../app_controller.dart';

class AdvancedApiPage extends StatefulWidget {
  const AdvancedApiPage({super.key, required this.controller});
  final AppController controller;
  @override
  State<AdvancedApiPage> createState() => _AdvancedApiPageState();
}

class _AdvancedApiPageState extends State<AdvancedApiPage> {
  final keyController = TextEditingController();
  final nameController = TextEditingController();
  final baseController = TextEditingController();
  final modelController = TextEditingController();
  String provider = 'openai';
  List<dynamic> credentials = [];
  List<dynamic> models = [];
  bool loading = true;

  bool get compatible => provider == 'openai_compatible';

  @override
  void initState() {
    super.initState();
    load();
  }

  @override
  void dispose() {
    keyController.dispose();
    nameController.dispose();
    baseController.dispose();
    modelController.dispose();
    super.dispose();
  }

  Future<void> load() async {
    try {
      final values = await Future.wait([
        widget.controller.api.request('/api/v1/credentials'),
        widget.controller.api.request('/api/v1/custom-models'),
      ]);
      if (mounted) {
        setState(() {
          credentials = values[0]['data'] as List<dynamic>? ?? [];
          models = values[1]['data'] as List<dynamic>? ?? [];
          loading = false;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() => loading = false);
      }
    }
  }

  Future<void> save() async {
    if (keyController.text.length < 8) {
      return;
    }
    if (compatible) {
      await widget.controller.api.request(
        '/api/v1/custom-models',
        method: 'POST',
        body: {
          'name': nameController.text,
          'base_url': baseController.text,
          'api_key': keyController.text,
          'model_id': modelController.text,
          'capabilities': ['chat'],
        },
      );
    } else {
      await widget.controller.api.request(
        '/api/v1/credentials',
        method: 'POST',
        body: {'provider': provider, 'api_key': keyController.text},
      );
    }
    keyController.clear();
    nameController.clear();
    baseController.clear();
    modelController.clear();
    await load();
  }

  Future<void> remove(String path) async {
    await widget.controller.api.request(path, method: 'DELETE');
    await load();
  }

  Future<void> testCredential(String id) async {
    try {
      await widget.controller.api.request(
        '/api/v1/credentials/$id/test',
        method: 'POST',
      );
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text('凭据连接验证通过')));
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text('凭据验证失败，请检查后重试')));
      }
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('模型与 API')),
    body: ListView(
      padding: const EdgeInsets.all(20),
      children: [
        const Text('凭据由轻青服务端加密保存，保存后不会再次显示明文。自定义端点只允许公网 HTTPS。'),
        const SizedBox(height: 20),
        DropdownButtonFormField<String>(
          initialValue: provider,
          decoration: const InputDecoration(
            labelText: '供应商',
            border: OutlineInputBorder(),
          ),
          items: const [
            DropdownMenuItem(value: 'openai', child: Text('OpenAI')),
            DropdownMenuItem(value: 'google', child: Text('Google Gemini')),
            DropdownMenuItem(value: 'qwen', child: Text('通义千问')),
            DropdownMenuItem(value: 'minimax', child: Text('MiniMax')),
            DropdownMenuItem(
              value: 'openai_compatible',
              child: Text('OpenAI 兼容服务'),
            ),
          ],
          onChanged: (value) => setState(() => provider = value ?? 'openai'),
        ),
        const SizedBox(height: 12),
        if (compatible) ...[
          TextField(
            controller: nameController,
            decoration: const InputDecoration(
              labelText: '显示名称',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: baseController,
            decoration: const InputDecoration(
              labelText: 'HTTPS Base URL',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: modelController,
            decoration: const InputDecoration(
              labelText: '模型 ID',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 12),
        ],
        TextField(
          controller: keyController,
          obscureText: true,
          decoration: const InputDecoration(
            labelText: 'API Key',
            border: OutlineInputBorder(),
          ),
        ),
        const SizedBox(height: 12),
        FilledButton.icon(
          onPressed: save,
          icon: const Icon(Icons.lock),
          label: const Text('加密保存'),
        ),
        const SizedBox(height: 28),
        Text('已配置凭据', style: Theme.of(context).textTheme.titleMedium),
        if (loading) const LinearProgressIndicator(),
        ...credentials.map(
          (item) => ListTile(
            title: Text(item['provider']?.toString() ?? '供应商'),
            subtitle: Text('••••${item['key_last4'] ?? ''}'),
            trailing: Wrap(
              spacing: 4,
              children: [
                IconButton(
                  icon: const Icon(Icons.network_check),
                  tooltip: '测试连接',
                  onPressed: () => testCredential(item['id'].toString()),
                ),
                IconButton(
                  icon: const Icon(Icons.delete_outline),
                  onPressed: () => remove('/api/v1/credentials/${item['id']}'),
                ),
              ],
            ),
          ),
        ),
        Text('我的模型', style: Theme.of(context).textTheme.titleMedium),
        ...models.map(
          (item) => ListTile(
            title: Text(item['display_name']?.toString() ?? '自定义模型'),
            subtitle: Text(item['remote_model_id']?.toString() ?? ''),
            trailing: IconButton(
              icon: const Icon(Icons.delete_outline),
              onPressed: () => remove('/api/v1/custom-models/${item['id']}'),
            ),
          ),
        ),
      ],
    ),
  );
}
