// 当页面滚动时，检查滚动的距离并修改导航栏样式
window.onscroll = function() {
    let navbar = document.getElementById("navbar");

    // 如果页面滚动超过50px，变小导航栏
    if (window.pageYOffset > 50) {
        navbar.classList.add("smaller");
    } else {
        navbar.classList.remove("smaller");
    }
};