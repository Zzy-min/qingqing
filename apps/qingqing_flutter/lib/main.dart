import 'package:flutter/material.dart';

import 'src/app_controller.dart';
import 'src/qingqing_app.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final controller = AppController();
  await controller.restoreSession();
  runApp(QingQingApp(controller: controller));
}
