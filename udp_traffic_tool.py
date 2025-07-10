import socket
import multiprocessing
import random
import time
import sys
import ctypes
import os
import argparse
import msvcrt
from threading import Thread

def clear_console():
    """清理控制台显示"""
    os.system('cls' if os.name == 'nt' else 'clear')

def display_warning():
    """显示安全警告和合法使用声明"""
    clear_console()
    print("=" * 90)
    print("UDP Traffic Generator - 网络安全压力测试工具")
    print("=" * 90)
    print("法律声明: ")
    print("1. 本工具仅可用于获得明确授权的安全测试")
    print("2. 禁止对任何未授权系统进行测试")
    print("3. 使用本工具即表示您同意承担所有法律责任")
    print("4. 开发者对任何非法使用不承担责任")
    print("=" * 90)
    print("使用前请确保您拥有: ")
    print("   a) 目标系统的书面授权")
    print("   b) 在隔离环境中操作")
    print("   c) 不使用公共互联网资源")
    print("=" * 90)
    
    # 等待用户确认
    if os.name == 'nt':
        print("按Enter确认了解并接受上述条款...")
        while msvcrt.kbhit(): 
            msvcrt.getch()  # 清空键盘缓冲区
        input()
    else:
        input("按Enter确认了解并接受上述条款...")
    clear_console()

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='UDP流量生成工具')
    parser.add_argument('--target', required=True, help='目标IP地址')
    parser.add_argument('--port', type=int, default=80, help='目标端口 (默认:80)')
    parser.add_argument('--threads', type=int, 
                        default=min(os.cpu_count() * 5, 200),  
                        help=f'工作进程数 (默认: {min(os.cpu_count() * 5, 200)})')
    parser.add_argument('--size', type=int, default=1024, 
                        help='数据包大小(500-65507, 默认:1024)')
    parser.add_argument('--duration', type=int, default=60, 
                        help='测试持续时间(秒, 默认:60)')
    parser.add_argument('--minimal', action='store_true', 
                        help='精简输出模式')
    parser.add_argument('--test-mode', action='store_true', 
                        help='测试模式(小规模测试)')
    return parser.parse_args()

def udp_worker(worker_id, args, terminate, packet_counter, byte_counter):
    """UDP数据包发送工作线程"""
    worker_sent = 0
    worker_bytes = 0
    try:
        payload = random.randbytes(args.size)
        
        # 创建UDP套接字
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(0.1)
        
        target = (args.target, args.port)
        
        # 工作循环
        while not terminate.is_set():
            try:
                # 发送UDP数据包
                sock.sendto(payload, target)
                
                # 更新本地计数器
                worker_sent += 1
                worker_bytes += len(payload)
                
                # 定期更新全局计数器
                if worker_sent % 100 == 0:
                    with packet_counter.get_lock():
                        packet_counter.value += worker_sent
                    with byte_counter.get_lock():
                        byte_counter.value += worker_bytes
                    worker_sent = 0
                    worker_bytes = 0
                    
            except Exception as e:
                if not args.minimal and time.time() % 5 < 0.1:  # 控制错误显示
                    print(f"Worker {worker_id} error: {str(e)[:50]}")
                continue
    finally:
        # 更新最终计数
        with packet_counter.get_lock():
            packet_counter.value += worker_sent
        with byte_counter.get_lock():
            byte_counter.value += worker_bytes
            
        # 关闭套接字
        try:
            sock.close()
        except:
            pass

def traffic_monitor(args, terminate, packet_counter, byte_counter):
    """实时流量监控和显示"""
    start_time = time.time()
    last_update = start_time
    
    # 初始显示
    if not args.minimal:
        print(f"\n{'-' * 80}")
        print(f"目标地址: {args.target}:{args.port}")
        print(f"工作进程: {args.threads} | 包大小: {args.size}字节")
        print(f"开始时间: {time.strftime('%H:%M:%S')}")
        print(f"预计时长: {args.duration}秒")
        print(f"{'-' * 80}")
        print("运行中... (Ctrl+C 停止)")
    
    try:
        prev_bytes = 0
        while not terminate.is_set():
            time.sleep(1)
            
            current_time = time.time()
            elapsed = current_time - start_time
            
            # 获取当前计数
            current_bytes = byte_counter.value
            current_packets = packet_counter.value
            
            # 计算带宽
            byte_rate = current_bytes - prev_bytes
            gbps = (byte_rate * 8) / (1024 ** 3)  # Gbps
            
            # 显示统计信息
            if not args.minimal and (current_time - last_update >= 1.0):
                sys.stdout.write(
                    f"\r[已运行: {int(elapsed):03d}s] "
                    f"包数: {current_packets:,} | "
                    f"数据: {current_bytes/(1024 * 1024):.1f}MB | "
                    f"带宽: {gbps:.2f}Gbps | "
                    f"剩余: {max(0, args.duration - int(elapsed))}s"
                )
                sys.stdout.flush()
                last_update = current_time
            
            prev_bytes = current_bytes
            
            # 检查是否超时
            if elapsed >= args.duration:
                terminate.set()
                
    except KeyboardInterrupt:
        terminate.set()
        if not args.minimal:
            print("\n用户中断请求...")
    except Exception as e:
        print(f"监控错误: {str(e)}")

def test_mode(args):
    """测试模式运行"""
    args.threads = min(args.threads, 10)
    args.duration = min(args.duration, 10)
    args.size = min(args.size, 512)
    print("\n[测试模式] 小规模运行: ")
    print(f"线程数: {args.threads} | 时长: {args.duration}s | 包大小: {args.size}字节")

def main():
    # 显示安全警告
    display_warning()
    
    # 解析参数
    args = parse_arguments()
    
    # 测试模式调整参数
    if args.test_mode:
        test_mode(args)
    
    # 创建终止信号
    terminate = multiprocessing.Event()
    
    # 创建共享计数器
    packet_counter = multiprocessing.Value(ctypes.c_ulonglong, 0)
    byte_counter = multiprocessing.Value(ctypes.c_ulonglong, 0)
    
    # 启动监控线程
    monitor_thread = Thread(
        target=traffic_monitor,
        args=(args, terminate, packet_counter, byte_counter)
    )
    monitor_thread.daemon = True
    monitor_thread.start()
    
    # 启动工作进程
    processes = []
    for i in range(args.threads):
        p = multiprocessing.Process(
            target=udp_worker,
            args=(i, args, terminate, packet_counter, byte_counter)
        )
        p.daemon = True
        processes.append(p)
        p.start()
        time.sleep(0.01)  # 避免瞬间启动过多进程
    
    # 等待监控线程结束
    try:
        monitor_thread.join()
    except KeyboardInterrupt:
        terminate.set()
        if not args.minimal:
            print("\n用户中断请求...")
    
    # 等待所有工作进程结束
    for p in processes:
        try:
            if p.is_alive():
                p.join(1)
        except:
            pass
    
    # 收集最终统计
    final_packets = packet_counter.value
    final_bytes = byte_counter.value
    elapsed = time.time() - monitor_thread.start_time if hasattr(monitor_thread, 'start_time') else args.duration
    
    # 显示最终报告
    print("\n\n" + "=" * 80)
    print("测试报告".center(80))
    print("=" * 80)
    print(f"{'目标地址:':<15} {args.target}:{args.port}")
    print(f"{'运行时间:':<15} {elapsed:.2f}秒")
    print(f"{'发送包数:':<15} {final_packets:,}")
    print(f"{'总数据量:':<15} {final_bytes/(1024 * 1024):.2f}MB")
    
    if elapsed > 0:
        avg_bandwidth = (final_bytes * 8) / (elapsed * 1024 ** 3)
        print(f"{'平均带宽:':<15} {avg_bandwidth:.4f}Gbps")
    
    print("\n建议:")
    print("1. 在目标系统上使用Wireshark或tcpdump验证流量")
    print("2. 检查系统日志和服务状态以评估影响")
    print("3. 完成后恢复系统配置")
    
    print("\n注意: 所有测试必须遵守适用法律和道德准则")
    print("=" * 80)

if __name__ == '__main__':
    # 多进程支持
    multiprocessing.freeze_support()
    
    # 错误处理
    try:
        main()
    except Exception as e:
        print(f"严重错误: {str(e)}")
        print("请提交issue: https://github.com/xiangfanobb/UDP-Traffic-Generator/issues")
