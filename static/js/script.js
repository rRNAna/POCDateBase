let lastScrollTop = 0; // 用于保存上一次的滚动位置
const navbar = document.querySelector('nav'); // 获取导航栏元素

// 监听滚动事件
window.addEventListener('scroll', function() {
    let scrollTop = window.pageYOffset || document.documentElement.scrollTop;
    if (scrollTop > lastScrollTop) {
        // 向下滚动时，隐藏导航栏
        navbar.style.top = '-60px'; // 调整隐藏的高度
        } else {
        // 向上滚动时，显示导航栏
        navbar.style.top = '0';
    }

    // 更新最后一次的滚动位置
    lastScrollTop = scrollTop <= 0 ? 0 : scrollTop; // 防止为负值
});